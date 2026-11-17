from fastapi import APIRouter, Request, Depends
from backend.routes.auth import current_user
from backend.schemas import CreateRoom
from backend.services.rooms import new_room, require_room
import secrets

router = APIRouter(prefix='/api/rooms')


@router.post('', status_code=201)
def create(body: CreateRoom, request: Request, user=Depends(current_user)):
    room = new_room(user, body.model_dump())
    room.update(room_id=secrets.token_hex(16), invite_code=secrets.token_urlsafe(6), title=body.title, config=body.model_dump(exclude={'title'}), agent_status={'run_id':None,'state':'idle','label':'Ready'})
    db = request.app.state.db
    db.put('room:' + room['room_id'], room)
    db.put('invite:' + room['invite_code'], room['room_id'])
    return room


@router.get('/{room_id}')
def snapshot(room_id: str, request: Request, user=Depends(current_user)):
    room = require_room(request.app.state.db, room_id, user['id'])
    room['messages'] = room['messages'][-50:]
    return room

from backend.schemas import JoinRoom
from fastapi import HTTPException
from backend.services.events import publish_event


@router.post('/join')
def join(body: JoinRoom, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    room_id = db.get('invite:' + body.invite_code)
    if room_id is None:
        raise HTTPException(404, 'Invite not found')
    with db.lock:
        room = db.get('room:' + room_id)
        if user['id'] not in [member['user_id'] for member in room['members']]:
            room['members'].append({'user_id':user['id'], 'name':user['name']})
            room['versions']['participant_version'] += 1
            room.update(active_target=None, review_plan=None, confirmations=[])
            db.put('room:' + room_id, room)
            publish_event(db, room_id, 'room.updated', {'changed':['members','versions','confirmations']})
        room = db.get('room:' + room_id)
    room['messages'] = room['messages'][-50:]
    return room
from pydantic import ValidationError
from backend.schemas import TripConfig


@router.patch('/{room_id}/trip')
async def trip(room_id: str, body: dict, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        try:
            config = TripConfig.model_validate(dict(room['config'], **body)).model_dump()
        except ValidationError:
            raise HTTPException(422, 'Invalid trip configuration')
        if config != room['config']:
            room['config'] = config
            room['versions']['constraint_version'] += 1
            room.update(active_target=None, review_plan=None, confirmations=[])
            db.put('room:' + room_id, room)
            publish_event(db, room_id, 'room.updated', {'changed':['config','versions','confirmations']})
    await request.app.state.jobs.enqueue(room_id, 'trip_changed')
    return snapshot(room_id, request, user)
