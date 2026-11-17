from fastapi import APIRouter, Request, Depends
from backend.routes.auth import current_user
from backend.schemas import Confirm, Activate
from backend.services.rooms import require_room
from backend.services.planning import record_confirmation, finalize_plan, activate_plan
from backend.services.events import publish_event

router = APIRouter(prefix='/api/rooms/{room_id}/plan')


@router.post('/confirm')
async def confirm(room_id: str, body: Confirm, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        record_confirmation(room, user['id'], body.target.model_dump(), 'confirm')
        finalized = finalize_plan(room)
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['review_plan','active_target','confirmations']})
        if finalized:
            publish_event(db, room_id, 'plan.confirmed', {'target':room['active_target']})
        room = require_room(db, room_id, user['id'])
    room['messages'] = room['messages'][-50:]
    return room
