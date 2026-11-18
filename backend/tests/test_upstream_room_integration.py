"""Upstream guarded jobs and observed places retain room lifecycle contracts."""
import asyncio
from copy import deepcopy

import pytest

from backend.db import Database


@pytest.mark.parametrize('raises', [False, True], ids=['returned-result', 'raised-error'])
def test_deleted_guarded_run_keeps_worker_alive_for_next_room(room, agent_result, raises):
    from backend.services.agent_jobs import AgentJobs
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        for room_id in ('gone', 'kept'):
            db.put('room:' + room_id, dict(deepcopy(room), room_id=room_id))

        class Port:
            async def run_current(self, task, emit, is_current):
                assert is_current()
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'], room_id=task['room_id'],
                              base_versions=task['base_versions'], plan_draft=None,
                              questions=[], observations=[], completion='done')
                if task['room_id'] == 'gone':
                    delete_room(db, 'gone', 'u1')
                    assert not is_current()
                    await emit(dict(run_id=task['run_id'], step=1, event='decision',
                                    call_id=None, created_at='2026-11-19T00:00:00Z', payload={}))
                    if raises:
                        raise RuntimeError('Deleted while the guarded run was active')
                return result

        jobs = AgentJobs(db, Port())
        deleted_run = await jobs.enqueue('gone', 'manual_replan')
        live_run = await jobs.enqueue('kept', 'manual_replan')
        worker = asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(), 2)
            assert not worker.done()
            assert db.get('room:kept')['agent_status']['state'] == 'done'
            assert db.get('run:' + live_run['run_id'])['applied'] is True
            assert db.get('room:gone') is None
            assert db.get('run:' + deleted_run['run_id']) is None
            assert 'gone' not in db.observations
            assert deleted_run['run_id'] not in db.traces
            assert [event['event'] for event in db.get('events:gone')] == ['room.deleted']
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            db.close()

    asyncio.run(scenario())


@pytest.mark.parametrize('reason', ['state_changed', 'remaining_messages', 'continue_pending'])
def test_deletion_at_internal_requeue_does_not_stop_shared_worker(room, agent_result, reason):
    from backend.services.agent_jobs import AgentJobs
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        saved = dict(deepcopy(room), room_id='gone')
        if reason == 'remaining_messages':
            saved['messages'] = [dict(saved['messages'][0], id=str(i), seq=i + 1) for i in range(21)]
        db.put('room:gone', saved)
        db.put('room:kept', dict(deepcopy(room), room_id='kept'))

        class Port:
            async def run_current(self, task, emit, is_current):
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'], room_id=task['room_id'],
                              base_versions=task['base_versions'], plan_draft=None,
                              questions=[], observations=[], completion='done')
                if task['room_id'] == 'gone':
                    if reason == 'state_changed':
                        updated = db.get('room:gone')
                        updated['versions']['constraint_version'] += 1
                        db.put('room:gone', updated)
                    elif reason == 'remaining_messages':
                        result['last_processed_message_id'] = task['recent_messages'][-1]['id']
                    else:
                        result['decision_report'] = dict(reason='round_limit')
                return result

        jobs = AgentJobs(db, Port())
        enqueue = jobs.enqueue
        deletion_reasons = []

        async def delete_before_enqueue(room_id, queued_reason, selection=None):
            if room_id == 'gone' and queued_reason == reason:
                deletion_reasons.append(queued_reason)
                delete_room(db, room_id, 'u1')
            return await enqueue(room_id, queued_reason, selection)

        jobs.enqueue = delete_before_enqueue
        gone = await jobs.enqueue('gone', 'manual_replan')
        await jobs.enqueue('kept', 'manual_replan')
        worker = asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(), 2)
            assert deletion_reasons == [reason]
            assert not worker.done()
            assert db.get('room:kept')['agent_status']['state'] == 'done'
            assert db.get('room:gone') is None
            assert db.get('run:' + gone['run_id']) is None
            assert 'gone' not in db.observations
            assert gone['run_id'] not in db.traces
            assert [event['event'] for event in db.get('events:gone')] == ['room.deleted']
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            db.close()

    asyncio.run(scenario())


def test_deletion_before_guarded_dispatch_skips_port_and_keeps_worker_alive(room, agent_result, monkeypatch):
    import backend.services.agent_jobs as service
    from backend.services.rooms import delete_room

    async def scenario():
        db = Database(':memory:')
        for room_id in ('gone', 'kept'):
            db.put('room:' + room_id, dict(deepcopy(room), room_id=room_id))
        set_status = service.set_status

        def delete_after_running_status(db, room_id, run_id, state, label):
            set_status(db, room_id, run_id, state, label)
            if room_id == 'gone' and state == 'running':
                delete_room(db, room_id, 'u1')

        monkeypatch.setattr(service, 'set_status', delete_after_running_status)

        class Port:
            async def run_current(self, task, emit, is_current):
                assert task['room_id'] == 'kept' and is_current()
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'], room_id='kept', base_versions=task['base_versions'],
                              plan_draft=None, questions=[], observations=[], completion='done')
                return result

        jobs = service.AgentJobs(db, Port())
        gone = await jobs.enqueue('gone', 'manual_replan')
        await jobs.enqueue('kept', 'manual_replan')
        worker = asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(), 2)
            assert not worker.done()
            assert db.get('room:kept')['agent_status']['state'] == 'done'
            assert db.get('run:' + gone['run_id']) is None
            assert [event['event'] for event in db.get('events:gone')] == ['room.deleted']
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            db.close()

    asyncio.run(scenario())


def test_room_snapshot_projects_places_and_retains_owner_and_listing_api(api, room):
    from backend.services.observations import project_observations

    db = api.app.state.db
    item = dict(room['items'][0], kind='place', title='돌산공원')
    room['items'] = [item]
    db.put('room:' + room['room_id'], room)
    project_observations(db, room['room_id'], [dict(
        tool_name='search_places', arguments=dict(region=room['config']['region']),
        source_refs=['observed-search'], result=dict(places=[dict(id='observed-park', name='돌산공원')]))])

    response = api.get('/api/rooms/' + room['room_id'])
    assert response.status_code == 200
    snapshot = response.json()
    assert snapshot['items'][0]['place_ref'] == 'observed-park'
    assert snapshot['owner_id'] == 'u1'
    summary = api.get('/api/rooms').json()['rooms'][0]
    assert summary['room_id'] == room['room_id']
    assert summary['owner_id'] == 'u1' and summary['is_owner'] is True


def test_location_only_read_uses_observations_without_calling_detail_provider(room):
    from backend.services.observations import fetch_place

    db = Database(':memory:')
    place = dict(id='observed-park', name='돌산공원', latitude=34.7, longitude=127.7)
    db.put('room:' + room['room_id'], room)
    db.observations[room['room_id']] = [dict(
        tool_name='search_places', arguments=dict(region=room['config']['region']),
        result=dict(places=[place]))]

    class Port:
        async def execute_tool(self, *args):
            pytest.fail('Coordinate reads must not invoke the detail provider')

    try:
        result = asyncio.run(fetch_place(db, Port(), room, 'observed-park', location_only=True))
        assert result['place'] == place
        assert result['menus'] == [] and result['evidence'] == []
        assert len(db.observations[room['room_id']]) == 1
    finally:
        db.close()
