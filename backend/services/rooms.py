import secrets
from copy import deepcopy
from fastapi import HTTPException


EMPTY_ROOM = {
    'seq': 0, 'messages': [], 'items': [], 'constraints': [],
    'versions': {'participant_version': 1, 'constraint_version': 0, 'evidence_version': 0, 'plan_revision': 0},
    'current_plan': None, 'review_plan': None, 'active_target': None,
    'confirmed_plan': None, 'confirmations': [], 'conflicts': [], 'questions': [],
    'agent_status': {'run_id': None, 'state': 'idle', 'label': '대기'},
}


def new_room(user, body):
    room = deepcopy(EMPTY_ROOM)
    room.update(room_id=secrets.token_hex(16), title=body['title'], invite_code=secrets.token_urlsafe(8), config={k: v for k, v in body.items() if k != 'title'}, members=[{'user_id': user['id'], 'name': user['name']}])
    return room


def require_room(db, room_id, viewer_id):
    room = db.get('room:' + room_id)
    if room is None:
        raise HTTPException(404, 'Room not found')
    if viewer_id not in [member['user_id'] for member in room['members']]:
        raise HTTPException(403, 'Room membership required')
    return room

from backend.domain import project_items


def get_room_snapshot(db, room_id, viewer_id):
    room = project_items(require_room(db, room_id, viewer_id))
    room['messages'] = room['messages'][-50:]
    return room
