"""Decisions must still match their complete room basis before tools or apply."""
import asyncio
import pytest


def empty_result(task):
    return dict(run_id=task['run_id'], room_id=task['room_id'], base_versions=task['base_versions'],
                constraint_proposals=[], item_proposals=[], support_observations=[], questions=[],
                conflicts=[], observations=[], plan_draft=None, completion='done', last_processed_message_id=None)


def change_room(db, room_id, field):
    if field == 'observations':
        db.observations[room_id] = [dict(tool_name='search_places', arguments={}, result={'places': []})]
        return
    updated = db.get('room:' + room_id)
    if field == 'versions':
        updated['versions']['constraint_version'] += 1
    elif field == 'config':
        updated['config']['region'] = '서울'
    elif field == 'items':
        updated['items'][0]['title'] = '수정된 장소'
    elif field == 'constraints':
        updated['constraints'][0]['value'] = 150000
    elif field == 'questions':
        updated['questions'][0].update(status='answered', answer='60', answered_by='u1')
    elif field == 'members':
        updated['members'][0]['name'] = '수정된 참가자'
    elif field == 'messages':
        updated['messages'].append(dict(updated['messages'][-1], id='late', text='새 요청'))
    elif field == 'current_plan':
        updated['current_plan'] = None
    db.put('room:' + room_id, updated)


@pytest.mark.parametrize('field', ['versions', 'config', 'items', 'constraints', 'questions',
                                 'messages', 'current_plan', 'members', 'observations'])
@pytest.mark.parametrize('supports_guard', [False, True])
def test_changed_decision_basis_blocks_old_apply_and_requeues(room, field, supports_guard):
    from backend.db import Database
    from backend.services.agent_jobs import AgentJobs
    async def scenario():
        db = Database(':memory:')
        room_id = room['room_id']
        db.put('room:' + room_id, room)
        calls, checks = [], []
        class Port:
            async def run(self, task, emit):
                assert not supports_guard
                return await perform(task, None)
        async def perform(task, guard):
            calls.append(task['run_id'])
            if guard:
                checks.append(guard())
            if len(calls) == 1:
                change_room(db, room_id, field)
                if guard:
                    checks.append(guard())
            return empty_result(task)
        async def run_current(task, emit, is_current):
            return await perform(task, is_current)
        port = Port()
        if supports_guard:
            port.run_current = run_current
        jobs = AgentJobs(db, port)
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue(room_id, 'replan')
        await asyncio.wait_for(jobs.queue.join(), 2)
        worker.cancel()
        assert len(calls) == 2
        assert not db.get('run:' + calls[0]).get('applied')
        assert db.get('run:' + calls[1])['applied'] is True
        if supports_guard:
            assert checks == [True, False, True]
    asyncio.run(scenario())


def test_trace_and_status_events_keep_same_snapshot_current(room):
    from backend.db import Database
    from backend.services.agent_jobs import AgentJobs, set_status
    async def scenario():
        db = Database(':memory:')
        db.put('room:' + room['room_id'], room)
        checks, runs = [], []
        class Port:
            async def run(self, task, emit):
                raise AssertionError('Must use the guarded port when provided')
            async def run_current(self, task, emit, is_current):
                runs.append(task['run_id'])
                checks.append(is_current())
                task['config']['region'] = 'private mutable model view'
                set_status(db, room['room_id'], task['run_id'], 'running', 'Comparing candidates')
                await emit(dict(run_id=task['run_id'], step=1, event='decision', call_id=None,
                                created_at='2026-11-18T00:00:00Z', payload={'summary': 'Judging'}))
                checks.append(is_current())
                return empty_result(task)
        jobs = AgentJobs(db, Port())
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue(room['room_id'], 'replan')
        await asyncio.wait_for(jobs.queue.join(), 2)
        worker.cancel()
        assert checks == [True, True]
        assert len(runs) == 1 and db.get('run:' + runs[0])['applied'] is True
        assert db.traces[runs[0]]['events'][0]['event'] == 'decision'
    asyncio.run(scenario())
