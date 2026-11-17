from backend.services.rooms import new_room


def test_new_room_has_contract_state():
    room = new_room({'id': 'u1', 'name': 'a'}, {'title': 'test'})
    assert room['members'] == [{'user_id': 'u1', 'name': 'a'}]
    assert room['active_target'] is None
    assert room['versions']['participant_version'] == 1


def test_room_membership_blocks_nonmember():
    import pytest
    from fastapi import HTTPException
    from backend.db import Database
    from backend.services.rooms import require_room
    db = Database(':memory:')
    db.put('room:r', new_room({'id':'u1','name':'a'}, {'title':'t'}))
    with pytest.raises(HTTPException) as error:
        require_room(db, 'r', 'u2')
    assert error.value.status_code == 403
