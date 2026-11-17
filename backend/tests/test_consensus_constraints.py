def test_support_author_matches_source_message(room):
    from backend.services.consensus import valid_support, support_threshold
    observation = dict(item_id='item-b', item_version=1, author_id='u4', stance='support', source_message_id='m4')
    assert support_threshold(4) == 3
    assert support_threshold(3) == 2
    assert valid_support(room, observation, 'u4')
    assert not valid_support(room, observation, 'u3')
    observation['item_version'] = 0
    assert not valid_support(room, observation, 'u4')


def test_support_is_unique_current_version_majority(room):
    from backend.services.consensus import apply_support
    item = room['items'][1]
    item['supporter_ids'] = []
    observation = dict(item_id='item-b', item_version=1, author_id='u4', stance='support', source_message_id='m4')
    apply_support(room, observation, 'u4')
    apply_support(room, observation, 'u4')
    assert item['supporter_ids'] == ['u4']
    assert item['state'] == 'mentioned'
    observation['stance'] = 'oppose'
    apply_support(room, observation, 'u4')
    assert item['supporter_ids'] == []
    assert item['opponent_ids'] == ['u4']


def test_constraint_relaxation_requires_owner(room):
    import pytest
    from fastapi import HTTPException
    from backend.services.consensus import edit_constraint
    original = room['constraints'][0]
    original['status'] = 'confirmed'
    previous = original['value']
    with pytest.raises(HTTPException):
        edit_constraint(room, original['id'], 'u4', 150000)
    pending = edit_constraint(room, original['id'], original['owner_id'], 150000)
    assert original['value'] == previous
    assert pending['status'] == 'needs_owner_confirmation'


def test_constraint_confirmation_supersedes_only_owner_key(room):
    from backend.services.consensus import edit_constraint, confirm_constraint
    original = room['constraints'][0]
    original['status'] = 'confirmed'
    owner = original['owner_id']
    pending = edit_constraint(room, original['id'], owner, 150000)
    confirm_constraint(room, pending['id'], owner)
    assert original['status'] == 'superseded'
    assert pending['status'] == 'confirmed'
    assert room['active_target'] is None


def test_constraint_edit_and_confirm_http_are_owner_only(api):
    path = '/api/rooms/room-fixture/constraints/constraint-budget'
    room = api.get('/api/rooms/room-fixture').json()
    constraint = room['constraints'][0]
    path = '/api/rooms/room-fixture/constraints/' + constraint['id']
    api.cookies.set('session','su4')
    assert api.patch(path, json={'value':150000}).status_code == 403
    api.cookies.set('session','s'+constraint['owner_id'])
    edited = api.patch(path, json={'value':150000})
    assert edited.status_code == 200
    response = api.post('/api/rooms/room-fixture/constraints/' + edited.json()['id'] + '/confirm')
    assert response.status_code == 200
    assert any(c['value'] == 150000 and c['status'] == 'confirmed' for c in response.json()['constraints'])
