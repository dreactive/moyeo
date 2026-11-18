"""A retained draft cannot replace another participant's accepted answer."""
from copy import deepcopy


def test_shared_question_rejects_second_participant_answer_without_side_effects(api, room, monkeypatch):
    db = api.app.state.db
    room['questions'] = [dict(
        id='shared-region', owner_id=None, field='region', target_ref='config:region',
        text='어느 지역으로 갈까요?', related_item_ids=[], status='open',
        answer=None, answered_by=None)]
    db.put('room:' + room['room_id'], room)
    jobs = []

    async def capture_enqueue(room_id, reason, selection=None):
        jobs.append((room_id, reason, selection))

    monkeypatch.setattr(api.app.state.jobs, 'enqueue', capture_enqueue)
    path = '/api/rooms/' + room['room_id'] + '/questions/shared-region/answer'
    first = api.post(path, json={'value': {'value': '부산'}})
    assert first.status_code == 200
    accepted = deepcopy(db.get('room:' + room['room_id']))
    events = deepcopy(db.get('events:' + room['room_id']))
    assert accepted['config']['region'] == '부산'
    assert accepted['versions']['constraint_version'] == room['versions']['constraint_version'] + 1
    assert accepted['questions'][0]['answered_by'] == 'u1'
    assert accepted['questions'][0]['answer'] == {'value': '부산'}
    assert jobs == [(room['room_id'], 'question_answered', None)]

    api.cookies.set('session', 'su2')
    second = api.post(path, json={'value': {'value': '제주'}})
    assert second.status_code == 409
    assert db.get('room:' + room['room_id']) == accepted
    assert db.get('events:' + room['room_id']) == events
    assert jobs == [(room['room_id'], 'question_answered', None)]
