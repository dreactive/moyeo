import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException

from backend.db import Database
from backend.services.agent_jobs import AgentJobs, make_task


def test_missing_dates_are_adapted_only_at_agent_boundary(room):
    room['config'].update(start_date=None, end_date=None, per_person_budget_krw=None)
    original = deepcopy(room['config'])
    task = make_task(room, 'run', 'manual_replan', [], None)
    assert task['config']['start_date']
    assert task['config']['start_date'] == task['config']['end_date']
    assert task['config']['per_person_budget_krw'] is None
    assert room['config'] == original
    for start, end, expected in [('2026-12-05', None, '2026-12-05'), (None, '2026-12-07', '2026-12-07')]:
        room['config'].update(start_date=start, end_date=end)
        task = make_task(room, 'run', 'manual_replan', [], None)
        assert task['config']['start_date'] == task['config']['end_date'] == expected


def test_worker_skips_deleted_queue_and_processes_next_room(room, agent_result):
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        for room_id in ('gone', 'kept'):
            saved = deepcopy(room)
            saved['room_id'] = room_id
            db.put('room:' + room_id, saved)

        class Port:
            async def run(self, task, emit):
                assert task['room_id'] == 'kept'
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'], room_id='kept', base_versions=task['base_versions'], plan_draft=None, questions=[], observations=[], completion='done')
                return result

        jobs = AgentJobs(db, Port())
        receipt = await jobs.enqueue('gone', 'manual_replan')
        await jobs.enqueue('kept', 'manual_replan')
        delete_room(db, 'gone', room['members'][0]['user_id'])
        worker = asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(), 2)
            assert db.get('room:gone') is None
            assert db.get('run:' + receipt['run_id']) is None
            assert db.get('room:kept')['agent_status']['state'] == 'done'
            with pytest.raises(HTTPException) as error:
                await jobs.enqueue('gone', 'manual_replan')
            assert error.value.status_code == 404
        finally:
            worker.cancel()

    asyncio.run(scenario())


def test_delete_during_agent_run_drops_late_result_and_all_room_caches(room, agent_result):
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        room_id = room['room_id']
        db.put('room:' + room_id, room)
        db.put('invite:' + room['invite_code'], room_id)
        db.put('processed-message:' + room_id, 'old')
        db.put('failed-extraction:' + room_id, {'m1': {'attempts': 1}})
        db.observations[room_id] = [{'tool_name': 'search_places', 'result': {'places': []}}]

        class Port:
            async def run(self, task, emit):
                event = dict(run_id=task['run_id'], step=1, event='decision', call_id=None, created_at='2026-11-19T00:00:00Z', payload={})
                await emit(event)
                assert task['run_id'] in db.traces
                delete_room(db, room_id, room['members'][0]['user_id'])
                await emit(dict(event, step=2))
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'], room_id=room_id, base_versions=task['base_versions'])
                return result

        jobs = AgentJobs(db, Port())
        receipt = await jobs.enqueue(room_id, 'manual_replan')
        worker = asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(), 2)
            assert db.get('room:' + room_id) is None
            assert db.get('invite:' + room['invite_code']) is None
            assert db.get('run:' + receipt['run_id']) is None
            assert db.get('processed-message:' + room_id) is None
            assert db.get('failed-extraction:' + room_id) is None
            assert room_id not in db.observations
            assert not db.traces
            assert db.get('events:' + room_id)[-1]['event'] == 'room.deleted'
            assert not worker.done()
        finally:
            worker.cancel()

    asyncio.run(scenario())


def test_stream_stops_after_delete_and_shutdown(room):
    from backend.services.events import room_event_stream
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        db.put('room:' + room['room_id'], room)
        stream = room_event_stream(db, room['room_id'], room['seq'])
        assert await anext(stream) == ': keepalive\n\n'
        delete_room(db, room['room_id'], room['members'][0]['user_id'])
        assert 'event: room.deleted\n' in await anext(stream)
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), 1)
        stopping = asyncio.Event()
        stream = room_event_stream(db, 'idle', 0, stopping)
        assert await anext(stream) == ': keepalive\n\n'
        pending = asyncio.create_task(anext(stream))
        await asyncio.sleep(.01)
        stopping.set()
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(pending, 1)

    asyncio.run(scenario())


def test_stale_join_invite_and_inflight_inviter_cannot_revive_deleted_room(room):
    from backend.services.rooms import add_member, delete_room

    db = Database(':memory:')
    db.put('room:' + room['room_id'], room)
    delete_room(db, room['room_id'], room['members'][0]['user_id'])
    with pytest.raises(HTTPException) as error:
        add_member(db, room['room_id'], {'id': 'late', 'name': 'Late'})
    assert error.value.status_code == 404


def test_inflight_place_lookup_cannot_recreate_deleted_room_observations(room, agent_result):
    from backend.services.observations import fetch_place
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        room_id = room['room_id']
        db.put('room:' + room_id, room)
        detail = agent_result['observations'][0]['result']
        db.observations[room_id] = [{'tool_name': 'search_places', 'arguments': {}, 'result': {'places': [detail['place']]}}]

        class Port:
            async def execute_tool(self, name, arguments, context):
                delete_room(db, room_id, room['members'][0]['user_id'])
                return detail

        with pytest.raises(HTTPException) as error:
            await fetch_place(db, Port(), room, detail['place']['id'])
        assert error.value.status_code == 404
        assert room_id not in db.observations

    asyncio.run(scenario())


def test_shutdown_signal_stops_streams_before_lifespan_shutdown(monkeypatch):
    import signal
    from backend.app import watch_shutdown_signals

    async def scenario():
        delegated = []
        def previous(signum, frame):
            delegated.append(signum)
        handlers = {}
        monkeypatch.setattr(signal, 'getsignal', lambda sig: previous)
        monkeypatch.setattr(signal, 'signal', lambda sig, handler: handlers.__setitem__(sig, handler))
        stopping = asyncio.Event()
        restore = watch_shutdown_signals(stopping)
        handlers[signal.SIGTERM](signal.SIGTERM, None)
        await asyncio.sleep(0)
        assert stopping.is_set()
        assert delegated == [signal.SIGTERM]
        restore()
        assert all(handler is previous for handler in handlers.values())

    asyncio.run(scenario())
