from backend.services.rooms import new_room


def test_new_room_has_contract_state():
    room = new_room({'id': 'u1', 'name': 'a'}, {'title': 'test'})
    assert room['members'] == [{'user_id': 'u1', 'name': 'a'}]
    assert room['active_target'] is None
    assert room['versions']['participant_version'] == 1
