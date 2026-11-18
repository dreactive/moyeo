"""Exercise the durable stages with the same grounding and dispatch as LocalAIBridge."""
import asyncio
from contextlib import closing
from contextvars import ContextVar
from copy import deepcopy

from ai.models.worker import ModelWorker
from ai.tests.test_auxiliary import analysis, batch, evidence
from ai.tests.test_judged_runner import Judge
from ai.tools.registry import RegisteredTools
from backend.adapters.local_ai import LocalAIBridge
from backend.db import Database
from backend.services.agent_jobs import AgentJobs
from backend.services.messages import save_message
from backend.services.observations import get_observations
from backend.tests.test_staged_agent_jobs import clean_room, stop


ROOM_ID = 'room-fixture'
PHASE = ContextVar('pipeline_test_phase', default=None)


def seed_room(db, fixture, room_id=ROOM_ID):
    value = clean_room(fixture, room_id)
    value['config'].update(region='여수', origin=None, destination=None, lodging=None, fixed_costs=[])
    db.put('room:' + room_id, value)


class ScriptedAuxiliary:
    def __init__(self, script):
        self.script, self.calls = script, []

    def extract(self, task, stage=1):
        assert PHASE.get() == 'extraction'
        source, = task['recent_messages']
        self.calls.append((source['id'], stage))
        return self.script(task, source, stage)


class ObservedBridge(LocalAIBridge):
    def __init__(self, script):
        super().__init__(dict(model_backend='fake', provider_mode='fixture', max_decision_rounds=3))
        self.auxiliary = ScriptedAuxiliary(script)
        self.judge = Judge()
        self.extracted = []
        self.signal = asyncio.Event()

    async def start(self):
        await super().start()
        self.runtime.auxiliary = self.auxiliary
        self.runtime.model = ModelWorker(self.judge)

    async def extract(self, task, previous=None):
        token = PHASE.set('extraction')
        try:
            result = await super().extract(task, previous)
        finally:
            PHASE.reset(token)
        self.extracted.append((tuple(m['id'] for m in task['recent_messages']), previous is not None))
        self.signal.set()
        return result

    async def run_prepared(self, task, prepared, emit_trace, is_current=None):
        token = PHASE.set('execution')
        try:
            return await super().run_prepared(task, prepared, emit_trace, is_current)
        finally:
            PHASE.reset(token)

    async def wait_for_extraction(self, message_id):
        while ((message_id,), False) not in self.extracted:
            self.signal.clear()
            await self.signal.wait()


def pause_first_search(monkeypatch, room_id):
    entered, release, calls = asyncio.Event(), asyncio.Event(), []
    execute = RegisteredTools.execute

    async def controlled(self, name, arguments):
        assert PHASE.get() == 'execution'
        current_room = self.context['room_id']
        calls.append((current_room, name, deepcopy(arguments)))
        if current_room == room_id and name == 'search_places' and not entered.is_set():
            entered.set()
            await release.wait()
        return await execute(self, name, arguments)

    monkeypatch.setattr(RegisteredTools, 'execute', controlled)
    return entered, release, calls


def lookup(source, *, target='오동도', cancel=False):
    fields = [] if cancel else ['location']
    return dict(intent='place_lookup', operation='cancel' if cancel else 'request',
                evidence=evidence(source['text'].split('.')[0], source['id']),
                target_names=[target], requested_fields=fields)


async def submit(db, jobs, text, author='u1', room_id=ROOM_ID):
    message = save_message(db, room_id, author, text)
    receipt = await jobs.enqueue(room_id, 'new_message')
    return message, receipt['run_id']


def test_inflight_lookup_defers_to_late_cancellation_and_reuses_read_after_restart(room, tmp_path, monkeypatch):
    async def scenario():
        def script(task, source, stage):
            conditions = []
            if '예산' in source['text']:
                conditions.append(dict(key='budget_krw', value=150000,
                    evidence=evidence('내 예산은 15만원이야', source['id'])))
            return batch(constraint_proposals=conditions,
                         analysis=analysis(requests=[lookup(source, target='가상 B공원', cancel='취소' in source['text'])]))

        db_path = tmp_path / 'lookup.sqlite3'
        bridge = ObservedBridge(script)
        await bridge.start()
        entered, release, calls = pause_first_search(monkeypatch, ROOM_ID)
        try:
            with closing(Database(db_path)) as db:
                seed_room(db, room)
                jobs = AgentJobs(db, bridge)
                worker = asyncio.create_task(jobs.work())
                try:
                    first, original_run = await submit(db, jobs, '가상 B공원 찾아줘. 내 예산은 15만원이야.')
                    await asyncio.wait_for(entered.wait(), 2)
                    cancel, _ = await submit(db, jobs, '가상 B공원 검색 취소해줘')
                    await asyncio.wait_for(bridge.wait_for_extraction(cancel['id']), 2)
                    assert db.get('processed-message:' + ROOM_ID) is None
                    assert len(calls) == 1
                    release.set()
                    await asyncio.wait_for(jobs.queue.join(), 5)
                    saved = db.get('room:' + ROOM_ID)
                    states = {r['source_message_id']: r for r in saved['agent_requests']}
                    assert states[first['id']]['status'] == 'cancelled'
                    assert states[cancel['id']]['status'] == 'completed'
                    assert [c['value'] for c in saved['constraints']] == [150000]
                    assert saved['current_plan'] is None
                    assert db.get('processed-message:' + ROOM_ID) == cancel['id']
                    assert len(calls) == 1
                    events = db.traces[original_run]['events']
                    result, = [e for e in events if e['event'] == 'tool_result']
                    assert 'arguments' not in result['payload']
                    assert result['payload']['normalized_result']['places']
                    assert any(e['event'] == 'state_applied' and e['payload']['applied'] for e in events)
                finally:
                    release.set()
                    await stop(worker)

            with closing(Database(db_path)) as db:
                jobs = AgentJobs(db, bridge)
                worker = asyncio.create_task(jobs.work())
                try:
                    await asyncio.wait_for(jobs.queue.join(), 5)
                    observation, = get_observations(db, ROOM_ID)
                    assert observation['arguments'] == dict(query='가상 B공원', region='여수', category=None)
                    again, _ = await submit(db, jobs, '가상 B공원 찾아줘', author='u2')
                    await asyncio.wait_for(jobs.queue.join(), 5)
                    result, = [r for r in db.get('room:' + ROOM_ID)['agent_requests']
                               if r['source_message_id'] == again['id']]
                    assert result['status'] == 'completed'
                    assert len(calls) == 1
                finally:
                    await stop(worker)
        finally:
            await bridge.aclose()

    asyncio.run(scenario())


def test_contextual_reply_refreshes_once_after_earlier_item_applies(room, monkeypatch):
    async def scenario():
        blocking_room = 'tool-blocker'

        def script(task, source, stage):
            quote = evidence(source['text'], source['id'])
            if task['room_id'] == blocking_room:
                return batch(analysis=analysis(requests=[lookup(source)]))
            if source['text'] == '오동도 가자':
                return batch(item_proposals=[dict(title='오동도', mention_text='오동도',
                    client_ref='odong', evidence=quote)],
                    support_observations=[dict(item_id='odong', item_version=1, stance='support', evidence=quote)])
            assert source['text'] == '응'
            if stage == 2 and task['items']:
                item, = task['items']
                previous, = task['conversation_context']
                return batch(support_observations=[dict(item_id=item['id'], item_version=item['item_version'],
                    stance='support', evidence=quote, context_message_ids=[previous['id']])])
            return batch(analysis=analysis(needs_context=True, context_queries=['오동도']))

        bridge = ObservedBridge(script)
        await bridge.start()
        entered, release, calls = pause_first_search(monkeypatch, blocking_room)
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            seed_room(db, room, blocking_room)
            jobs = AgentJobs(db, bridge)
            worker = asyncio.create_task(jobs.work())
            try:
                await submit(db, jobs, '오동도 찾아줘', room_id=blocking_room)
                await asyncio.wait_for(entered.wait(), 2)
                first, _ = await submit(db, jobs, '오동도 가자')
                reply, _ = await submit(db, jobs, '응', author='u2')
                await asyncio.wait_for(bridge.wait_for_extraction(reply['id']), 2)
                assert db.get('room:' + ROOM_ID)['items'] == []
                assert len(calls) == 1
                release.set()
                await asyncio.wait_for(jobs.queue.join(), 5)
                saved = db.get('room:' + ROOM_ID)
                item, = saved['items']
                assert item['title'] == '오동도'
                assert item['source_message_ids'] == [first['id']]
                assert sorted(item['supporter_ids']) == ['u1', 'u2']
                assert [stage for mid, stage in bridge.auxiliary.calls if mid == first['id']] == [1]
                assert [stage for mid, stage in bridge.auxiliary.calls if mid == reply['id']] == [1, 2, 2]
                assert [refresh for ids, refresh in bridge.extracted if ids == (reply['id'],)] == [False, True]
                assert db.get('processed-message:' + ROOM_ID) == reply['id']
            finally:
                release.set()
                await stop(worker)
                await bridge.aclose()

    asyncio.run(scenario())
