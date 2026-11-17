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
