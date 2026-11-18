"""Recovery fences and dispatch ordering using isolated SQLite and fixture tools."""
import asyncio
from contextlib import closing

import pytest

from ai.tests.test_auxiliary import analysis, batch
from ai.tests.test_review_request_lifecycle import saved
from ai.tools.registry import RegisteredTools
from backend.db import Database
from backend.services.agent_pipeline import PipelineJobs
from backend.services.messages import save_message
from backend.tests.test_pipeline_runtime import ROOM_ID, ObservedBridge, lookup, seed_room, submit
from backend.tests.test_staged_agent_jobs import StagedPort, result_for, stop


async def next_stage(jobs, stage):
    job = jobs.store.claim(stage)
    assert job is not None
    await getattr(jobs, '_extract' if stage == 'extraction' else '_execute')(job)
    return job


async def finish(jobs):
    await next_stage(jobs, 'extraction')
    return await next_stage(jobs, 'execution')


class RequestPort(StagedPort):
    def __init__(self):
        super().__init__()
        self.calls = []

    async def run_prepared(self, task, prepared, emit, is_current=None):
        result = result_for(task)
        requests = [saved(m['id'], m['text'].split()[0]) for m in task['recent_messages']]
        requests = requests or task['pending_requests']
        if task.get('_defer_execution'):
            result['decision_report'] = dict(status='held', reason='newer_messages_pending')
        else:
            self.calls.extend(r['request_id'] for r in requests)
            requests = [dict(r, status='completed') for r in requests]
        result['request_states'] = requests
        return result


def test_source_free_continuation_waits_for_later_cancellation_even_after_failed_extraction(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            port = RequestPort()
            jobs = PipelineJobs(db, port)
            first = save_message(db, ROOM_ID, 'u1', '돌산공원 찾아줘')
            request = saved(first['id'], '돌산공원')
            value = db.get('room:' + ROOM_ID)
            value['agent_requests'] = [request]
            db.put_many({'room:' + ROOM_ID: value, 'processed-message:' + ROOM_ID: first['id']})
            await jobs.enqueue(ROOM_ID, 'continue_pending', resume_ids=[request['request_id']])
            await submit(db, jobs, '돌산공원 검색 취소해줘')
            await next_stage(jobs, 'extraction')
            assert jobs.store.fail(jobs.store.claim('extraction'), 'TimeoutError')
            await next_stage(jobs, 'execution')
            await jobs.reconcile()
            assert port.calls == []
            assert len(jobs.store.jobs()) == 2
            assert db.get('room:' + ROOM_ID)['agent_requests'][0]['status'] == 'pending'
            assert jobs.store.jobs()[0]['outcome']['reason'] == 'deferred_to_newer_input'

    asyncio.run(scenario())


def test_deferred_source_obligation_survives_failed_newer_input_until_retry(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            port = RequestPort()
            jobs = PipelineJobs(db, port)
            first, _ = await submit(db, jobs, '돌산공원 찾아줘')
            later, _ = await submit(db, jobs, '자산공원 찾아줘')
            await next_stage(jobs, 'extraction')
            assert jobs.store.fail(jobs.store.claim('extraction'), 'TimeoutError')
            await next_stage(jobs, 'execution')
            await jobs.reconcile()
            assert len(jobs.store.jobs()) == 2
            assert port.calls == []
            await jobs.enqueue(ROOM_ID, 'manual_replan')
            await finish(jobs)
            await finish(jobs)
            assert port.calls == [saved(mid, '')['request_id'] for mid in (later['id'], first['id'])]
    asyncio.run(scenario())


@pytest.mark.parametrize('subset_size', [1, 2])
def test_targeted_resume_keeps_ambiguous_cancellation_scope(room, monkeypatch, subset_size):
    async def scenario():
        def script(task, source, stage):
            cancel = '취소' in source['text']
            request = lookup(source, target=source['text'].split()[0], cancel=cancel)
            if cancel:
                request['target_names'] = []
            return batch(analysis=analysis(requests=[request]))

        calls = []
        execute = RegisteredTools.execute

        async def record(tools, name, arguments):
            calls.append((name, arguments))
            return await execute(tools, name, arguments)

        monkeypatch.setattr(RegisteredTools, 'execute', record)
        bridge = ObservedBridge(script)
        await bridge.start()
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            jobs = PipelineJobs(db, bridge)
            try:
                await submit(db, jobs, '돌산공원 찾아줘')
                await submit(db, jobs, '자산공원 찾아줘')
                await submit(db, jobs, '조회 취소해줘')
                for _ in range(2):
                    await finish(jobs)
                states = db.get('room:' + ROOM_ID)['agent_requests']
                originals = [r['request_id'] for r in states if r['operation'] == 'request']
                assert len(originals) == 2
                await jobs.enqueue(ROOM_ID, 'continue_pending', resume_ids=originals[:subset_size])
                await finish(jobs)
                states = db.get('room:' + ROOM_ID)['agent_requests']
                assert any(r['operation'] == 'cancel' and r['status'] == 'needs_input' for r in states)
                await finish(jobs)
                assert calls == []
                values = db.get('room:' + ROOM_ID)['agent_requests']
                assert all(r['status'] not in ('cancelled', 'completed') for r in values)
            finally:
                await bridge.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize('phase', ['failed', 'held'])
def test_manual_retry_recovers_pre_cursor_durable_gap_exactly_once(room, phase):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            jobs = PipelineJobs(db, StagedPort())
            first, _ = await submit(db, jobs, 'A')
            second, _ = await submit(db, jobs, 'B')
            await next_stage(jobs, 'extraction')
            claimed = jobs.store.claim('execution')
            db.put_many(jobs.store.completion_records(claimed, dict(phase=phase, reason='fixture')))
            await finish(jobs)
            assert db.get('processed-message:' + ROOM_ID) == second['id']
            await jobs.enqueue(ROOM_ID, 'manual_replan')
            retry = await finish(jobs)
            assert retry['message_ids'] == [first['id']]
            assert db.get('processed-message:' + ROOM_ID) == second['id']
            await jobs.enqueue(ROOM_ID, 'manual_replan')
            assert jobs.store.jobs()[-1]['message_ids'] == []
    asyncio.run(scenario())


def test_unrelated_extraction_reconcile_between_two_reads_preserves_decision_snapshot(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            seed_room(db, room, 'other')

            class TwoReads(StagedPort):
                async def run_prepared(self, task, prepared, emit, is_current=None):
                    for step in (1, 2):
                        assert is_current()
                        fields = dict(run_id=task['run_id'], step=step, call_id=f"{task['run_id']}:{step}",
                                      created_at='2026-11-19T00:00:00Z')
                        await emit(dict(fields, event='tool_call', payload=dict(tool_name='search_places',
                                        arguments={'query': str(step)})))
                        await emit(dict(fields, event='tool_result', payload=dict(tool_name='search_places',
                                        normalized_result={'places': []})))
                        await submit(db, jobs, str(step), room_id='other')
                        await next_stage(jobs, 'extraction')
                        await jobs.reconcile()
                    return result_for(task)

            jobs = PipelineJobs(db, TwoReads())
            await submit(db, jobs, 'search twice')
            await finish(jobs)
            job = jobs.store.jobs(ROOM_ID)[0]
            assert job['phase'] == 'done' and job['execution_attempts'] == 1
            assert len(jobs.store.restore_observations(ROOM_ID)) == 2
    asyncio.run(scenario())


class InterruptedAfterApply(BaseException):
    pass


async def crash_after_apply(jobs, monkeypatch):
    import backend.services.agent_pipeline as pipeline
    apply = pipeline.apply_agent_result

    def interrupted(*args, **kwargs):
        assert apply(*args, **kwargs)
        raise InterruptedAfterApply()

    with monkeypatch.context() as patch:
        patch.setattr(pipeline, 'apply_agent_result', interrupted)
        with pytest.raises(InterruptedAfterApply):
            await next_stage(jobs, 'execution')


def test_round_limit_intent_survives_apply_crash_and_is_idempotent_and_bounded(room, monkeypatch):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)

            class RoundLimit(StagedPort):
                async def run_prepared(self, task, prepared, emit, is_current=None):
                    result = result_for(task)
                    requests = task['pending_requests']
                    if task['recent_messages']:
                        requests = [saved(task['recent_messages'][0]['id'], '돌산공원')]
                    return dict(result, request_states=requests, completion='needs_input',
                                decision_report=dict(status='held', reason='round_limit'))

            jobs = PipelineJobs(db, RoundLimit())
            await submit(db, jobs, '돌산공원 찾아줘')
            await next_stage(jobs, 'extraction')
            await crash_after_apply(jobs, monkeypatch)
            jobs = PipelineJobs(db, RoundLimit())
            jobs.store.recover()
            await jobs.reconcile()
            assert len(jobs.store.jobs()) == 2
            await jobs.reconcile()
            await finish(jobs)
            await finish(jobs)
            await jobs.reconcile()
            assert [j['task']['_continuation_depth'] for j in jobs.store.jobs()] == [0, 1, 2]
            assert all(j['phase'] == 'done' for j in jobs.store.jobs())
    asyncio.run(scenario())


@pytest.mark.parametrize('at_limit', [False, True])
def test_startup_rebuilds_terminal_room_status_and_counts(room, monkeypatch, at_limit):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            jobs = PipelineJobs(db, StagedPort())
            await submit(db, jobs, 'A')
            if at_limit:
                jobs.store.max_attempts = 1
                jobs.store.claim('extraction')
                jobs._progress(ROOM_ID)
            else:
                await next_stage(jobs, 'extraction')
                await crash_after_apply(jobs, monkeypatch)
            jobs = PipelineJobs(db, StagedPort())
            if at_limit:
                jobs.store.max_attempts = 1
            worker = asyncio.create_task(jobs.work())
            try:
                await asyncio.wait_for(jobs.queue.join(), 2)
                value = db.get('room:' + ROOM_ID)
                phase = 'failed' if at_limit else 'done'
                assert value['agent_status']['state'] == phase
                assert value['agent_pipeline']['counts'][phase] == 1
                assert value['agent_pipeline']['counts']['extracting'] == 0
                assert value['agent_pipeline']['counts']['executing'] == 0
            finally:
                await stop(worker)
    asyncio.run(scenario())



@pytest.mark.parametrize('kind, owner, target, expected_status', [
    ('cancel', 'u1', '돌산공원', 'cancelled'),
    ('cancel', 'u2', '돌산공원', 'completed'),
    ('cancel', 'u1', '자산공원', 'completed'),
    ('correct', 'u1', '돌산공원', 'superseded')])
def test_historical_retry_respects_later_request_scope(room, monkeypatch, kind, owner, target, expected_status):
    async def scenario():
        def script(task, source, stage):
            name = source['text'].split()[0]
            request = lookup(source, target=name, cancel='취소' in source['text'])
            if '말고' in source['text']:
                request.update(target_names=['오동도'], excluded_names=['돌산공원'])
            return batch(analysis=analysis(requests=[request]))

        calls = []
        execute = RegisteredTools.execute

        async def record(tools, name, arguments):
            calls.append((name, arguments))
            return await execute(tools, name, arguments)

        monkeypatch.setattr(RegisteredTools, 'execute', record)
        bridge = ObservedBridge(script)
        await bridge.start()
        try:
            with closing(Database(':memory:')) as db:
                seed_room(db, room)
                jobs = PipelineJobs(db, bridge)
                first, _ = await submit(db, jobs, '돌산공원 찾아줘')
                assert jobs.store.fail(jobs.store.claim('extraction'), 'TimeoutError')
                message = target + ' 검색 취소해줘' if kind == 'cancel' else '돌산공원 말고 오동도 찾아줘'
                later, _ = await submit(db, jobs, message, author=owner)
                await finish(jobs)
                control, = db.get('room:' + ROOM_ID)['agent_requests']
                assert control['source_message_id'] == later['id'] and control['status'] == 'completed'
                calls.clear()
                await jobs.enqueue(ROOM_ID, 'manual_replan')
                await finish(jobs)
                worker = asyncio.create_task(jobs.work())
                try:
                    await asyncio.wait_for(jobs.queue.join(), 3)
                    assert len(calls) == (1 if expected_status == 'completed' else 0)
                    states = db.get('room:' + ROOM_ID)['agent_requests']
                    assert next(r for r in states if r['source_message_id'] == later['id']) == control
                    recovered = next(r for r in states if r['source_message_id'] == first['id'])
                    assert recovered['status'] == expected_status
                finally:
                    await stop(worker)
        finally:
            await bridge.aclose()
    asyncio.run(scenario())


def test_control_without_request_ids_reconciles_original_goal_after_catchup(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            dispatches = []

            class Control(StagedPort):
                async def run_prepared(self, task, prepared, emit, is_current=None):
                    value = result_for(task)
                    if task.get('_defer_execution'):
                        value['decision_report'] = dict(status='held', reason='newer_messages_pending')
                    elif task['goal'] == 'trip_changed':
                        dispatches.append(task['goal'])
                    return value

            jobs = PipelineJobs(db, Control())
            await jobs.enqueue(ROOM_ID, 'trip_changed')
            await submit(db, jobs, 'A')
            await finish(jobs)
            assert dispatches == []
            await finish(jobs)
            worker = asyncio.create_task(jobs.work())
            try:
                await asyncio.wait_for(jobs.queue.join(), 3)
                assert dispatches == ['trip_changed']
            finally:
                await stop(worker)
    asyncio.run(scenario())


def test_parked_conflict_selection_keeps_accepted_versions(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            port = StagedPort()
            jobs = PipelineJobs(db, port)
            versions = db.get('room:' + ROOM_ID)['versions']
            selection = dict(base_versions=versions, effect=dict(kind='drop_visit', item_id='older-item'))
            await jobs.enqueue(ROOM_ID, 'conflict_selected', selection)
            await submit(db, jobs, 'A')
            await finish(jobs)
            updated = db.get('room:' + ROOM_ID)
            updated['versions']['constraint_version'] += 1
            db.put('room:' + ROOM_ID, updated)
            await finish(jobs)
            worker = asyncio.create_task(jobs.work())
            try:
                await asyncio.wait_for(jobs.queue.join(), 3)
                child = jobs.store.jobs()[-1]
                assert child['task']['user_selection']['base_versions'] == versions
                assert child['phase'] in ('failed', 'held')
                assert not db.get('run:' + child['run_id']).get('applied')
                assert len(port.executed) == 1
            finally:
                await stop(worker)
    asyncio.run(scenario())


def test_retry_of_older_cancellation_cannot_retire_future_request(room):
    async def scenario():
        def script(task, source, stage):
            return batch(analysis=analysis(requests=[lookup(source, target='돌산공원', cancel=True)]))

        bridge = ObservedBridge(script)
        await bridge.start()
        try:
            with closing(Database(':memory:')) as db:
                seed_room(db, room)
                jobs = PipelineJobs(db, StagedPort())
                await submit(db, jobs, '돌산공원 검색 취소해줘')
                assert jobs.store.fail(jobs.store.claim('extraction'), 'TimeoutError')
                future, _ = await submit(db, jobs, '돌산공원 찾아줘')
                await finish(jobs)
                pending = saved(future['id'], '돌산공원')
                value = db.get('room:' + ROOM_ID)
                value['agent_requests'] = [pending]
                db.put('room:' + ROOM_ID, value)
                jobs = PipelineJobs(db, bridge)
                await jobs.enqueue(ROOM_ID, 'manual_replan')
                worker = asyncio.create_task(jobs.work())
                try:
                    await asyncio.wait_for(jobs.queue.join(), 3)
                    states = db.get('room:' + ROOM_ID)['agent_requests']
                    assert next(r for r in states if r['request_id'] == pending['request_id']) == pending
                    control, = [r for r in states if r.get('operation') == 'cancel']
                    assert control['prior_request_ids'] == []
                finally:
                    await stop(worker)
        finally:
            await bridge.aclose()
    asyncio.run(scenario())


def test_recovered_batch_reopens_ambiguous_generic_no_target_cancellation(room, monkeypatch):
    async def scenario():
        class BatchAuxiliary:
            def extract(self, task, stage=1):
                requests = []
                for source in task['recent_messages']:
                    cancel = '취소' in source['text']
                    request = lookup(source, target=source['text'].split()[0], cancel=cancel)
                    if cancel:
                        request['target_names'] = []
                    requests.append(request)
                return batch(analysis=analysis(requests=requests))

        calls = []
        execute = RegisteredTools.execute

        async def record(tools, name, arguments):
            calls.append((name, arguments))
            return await execute(tools, name, arguments)

        monkeypatch.setattr(RegisteredTools, 'execute', record)
        bridge = ObservedBridge(None)
        bridge.auxiliary = BatchAuxiliary()
        await bridge.start()
        try:
            with closing(Database(':memory:')) as db:
                seed_room(db, room)
                jobs = PipelineJobs(db, bridge)
                sources = [save_message(db, ROOM_ID, 'u1', name + ' 찾아줘')
                           for name in ('돌산공원', '자산공원')]
                await jobs.enqueue(ROOM_ID, 'new_message')
                assert jobs.store.fail(jobs.store.claim('extraction'), 'TimeoutError')
                cancellation, _ = await submit(db, jobs, '조회 취소해줘')
                await finish(jobs)
                control, = db.get('room:' + ROOM_ID)['agent_requests']
                assert control['status'] == 'completed' and not control['cancelled_request_ids']
                await jobs.enqueue(ROOM_ID, 'manual_replan')
                worker = asyncio.create_task(jobs.work())
                try:
                    await asyncio.wait_for(jobs.queue.join(), 3)
                    value = db.get('room:' + ROOM_ID)
                    states = {r['source_message_id']: r for r in value['agent_requests']}
                    assert all(states[s['id']]['status'] not in ('cancelled', 'completed') for s in sources)
                    assert states[cancellation['id']]['status'] == 'needs_input'
                    assert any(q['target_ref'] == control['request_id'] and q['status'] == 'open'
                               for q in value['questions'])
                    assert calls == []
                finally:
                    await stop(worker)
        finally:
            await bridge.aclose()
    asyncio.run(scenario())


@pytest.mark.parametrize('later_status', ['pending', 'resolved'])
def test_historical_retry_honors_open_explicit_correction(room, monkeypatch, later_status):
    async def scenario():
        def script(task, source, stage):
            return batch(analysis=analysis(requests=[lookup(source, target='돌산공원')]))

        calls = []
        execute = RegisteredTools.execute

        async def record(tools, name, arguments):
            calls.append((name, arguments))
            return await execute(tools, name, arguments)

        monkeypatch.setattr(RegisteredTools, 'execute', record)
        bridge = ObservedBridge(script)
        await bridge.start()
        try:
            with closing(Database(':memory:')) as db:
                seed_room(db, room)
                jobs = PipelineJobs(db, StagedPort())
                older, _ = await submit(db, jobs, '돌산공원 찾아줘')
                assert jobs.store.fail(jobs.store.claim('extraction'), 'TimeoutError')
                later, _ = await submit(db, jobs, '돌산공원 말고 오동도 찾아줘')
                await finish(jobs)
                value = db.get('room:' + ROOM_ID)
                correction = dict(saved(later['id'], '오동도'), status=later_status,
                                  excluded_names=['돌산공원'])
                correction['evidence']['quote'] = later['text']
                value['agent_requests'] = [correction]
                db.put('room:' + ROOM_ID, value)
                jobs = PipelineJobs(db, bridge)
                await jobs.enqueue(ROOM_ID, 'manual_replan')
                worker = asyncio.create_task(jobs.work())
                try:
                    await asyncio.wait_for(jobs.queue.join(), 3)
                    states = {r['source_message_id']: r for r in db.get('room:' + ROOM_ID)['agent_requests']}
                    assert states[older['id']]['status'] == 'superseded'
                    assert states[later['id']] == correction
                    assert calls == []
                finally:
                    await stop(worker)
        finally:
            await bridge.aclose()
    asyncio.run(scenario())


def test_calculation_only_round_continues_at_same_depth_after_parking(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            decisions = []

            class PlanRounds(StagedPort):
                async def run_prepared(self, task, prepared, emit, is_current=None):
                    result = result_for(task)
                    if task['goal'] in ('trip_changed', 'continue_pending'):
                        decisions.append((task['goal'], task['_continuation_depth']))
                        result.update(completion='needs_input', decision_report=dict(status='held', reason='round_limit'))
                    return result

            jobs = PipelineJobs(db, PlanRounds())
            await jobs.enqueue(ROOM_ID, 'trip_changed')
            await finish(jobs)
            await submit(db, jobs, 'new source')
            await finish(jobs)
            assert jobs.store.jobs()[1]['phase'] == 'held'
            await finish(jobs)
            worker = asyncio.create_task(jobs.work())
            try:
                await asyncio.wait_for(jobs.queue.join(), 3)
                assert decisions == [('trip_changed', 0), ('continue_pending', 1), ('continue_pending', 2)]
                await jobs.reconcile()
                assert len(jobs.store.jobs()) == 5
            finally:
                await stop(worker)
    asyncio.run(scenario())


def test_execution_trace_distinguishes_same_call_id_on_retry(room):
    async def scenario():
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            jobs = PipelineJobs(db, StagedPort())
            _, run_id = await submit(db, jobs, 'search')
            await next_stage(jobs, 'extraction')
            call_id = run_id + ':1'
            for attempt in (1, 2):
                job = jobs.store.claim('execution')
                await jobs._trace(job, 'execution', 'started')
                fields = dict(run_id=run_id, step=1, call_id=call_id, created_at='2026-11-19T00:00:00Z')
                await jobs._emit(job, dict(fields, event='tool_call', payload=dict(
                    tool_name='search_places', arguments={'query': 'A'})))
                await jobs._emit(job, dict(fields, event='tool_result', payload=dict(
                    tool_name='search_places', normalized_result={'places': []})))
                if attempt == 1:
                    assert jobs.store.requeue(job, 'execution', 'state_changed')
            events = [e for e in db.traces[run_id]['events'] if e['event'] in ('execution', 'tool_call', 'tool_result')]
            assert len(events) == 6
            for i, event in enumerate(events):
                attempt = 1 + i // 3
                assert event['payload'].get('execution_id') == f'{run_id}:execution:{attempt}'
                assert event['payload']['attempt'] == attempt
                if event['event'] != 'execution':
                    assert event['call_id'] == call_id
                if event['event'] == 'tool_call':
                    assert event['payload']['arguments'] == {'query': 'A'}
                assert 'token' not in event['payload']
    asyncio.run(scenario())
