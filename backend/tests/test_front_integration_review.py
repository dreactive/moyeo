import asyncio
from copy import deepcopy
from datetime import date

import pytest

from backend.db import Database
from backend.services.rooms import room_summary, delete_room


def test_room_list_does_not_advertise_archived_confirmation_after_inputs_change(room):
    target = room['current_plan']['confirmation_target']
    room['versions'].update({key:target[key] for key in ('participant_version','constraint_version','evidence_version')})
    room['review_plan'] = None
    room['confirmed_plan'] = deepcopy(room['current_plan'])
    assert room_summary(room, 'u1')['plan_stage'] == 'confirmed'
    room['versions']['participant_version'] += 1
    assert room_summary(room, 'u1')['plan_stage'] == 'draft'
    room['current_plan']['plan_revision'] += 1
    room['current_plan']['confirmation_target']['plan_revision'] += 1
    assert room_summary(room, 'u1')['plan_revision'] == room['current_plan']['plan_revision']
    room['current_plan'] = None
    assert room_summary(room, 'u1')['plan_stage'] == 'empty'


@pytest.mark.parametrize('start,end', [(None,None), ('2026-12-05',None), (None,'2026-12-07')])
def test_uncached_place_lookup_adapts_optional_dates_without_changing_room(room, agent_result, start, end):
    from backend.services.observations import fetch_place, project_observations
    db = Database(':memory:')
    room['config'].update(start_date=start,end_date=end,per_person_budget_krw=None)
    original = deepcopy(room['config'])
    detail = deepcopy(agent_result['observations'][0]['result'])
    place = detail['place']
    db.put('room:' + room['room_id'], room)
    project_observations(db, room['room_id'], [{'tool_name':'search_places','arguments':{},'result':{'places':[place]}}])

    class StrictPort:
        async def execute_tool(self, name, arguments, context):
            assert name == 'get_place_details'
            assert arguments == {'place_ref':place['id']}
            config = context['config']
            assert date.fromisoformat(config['start_date']) == date.fromisoformat(config['end_date'])
            if start or end:
                assert config['start_date'] == (start or end)
            assert config['per_person_budget_krw'] is None
            return detail

    try:
        assert asyncio.run(fetch_place(db, StrictPort(), room, place['id'])) == detail
        assert db.get('room:' + room['room_id'])['config'] == original
        assert room['config'] == original
    finally:
        db.close()


def test_delete_purges_archived_plans_and_message_events_but_keeps_terminal_event(room):
    from backend.services.messages import save_message
    db = Database(':memory:')
    room_id = room['room_id']
    db.put('room:' + room_id, room)
    db.put('confirmed-history:' + room_id, [room['current_plan']])
    save_message(db, room_id, 'u1', 'private message to remove')
    try:
        delete_room(db, room_id, 'u1')
        assert db.get('confirmed-history:' + room_id) is None
        events = db.get('events:' + room_id)
        assert len(events) == 1
        assert events[0]['event'] == 'room.deleted'
        assert set(events[0]['data']) == {'room_id','seq'}
    finally:
        db.close()


def test_message_deleted_between_route_check_and_write_returns_not_found(api, monkeypatch):
    import backend.routes.messages as routes
    original = routes.save_message

    def delete_before_save(db, room_id, author_id, text):
        delete_room(db, room_id, author_id)
        return original(db, room_id, author_id, text)

    monkeypatch.setattr(routes, 'save_message', delete_before_save)
    response = api.post('/api/rooms/room-fixture/messages', json={'text':'arrived during deletion'})
    assert response.status_code == 404
