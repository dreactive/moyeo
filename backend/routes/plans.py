from backend.routes.auth import current_user
from backend.schemas import Confirm, Activate
from backend.services.events import publish_event
from backend.services.planning import record_confirmation, finalize_plan, activate_plan
from backend.services.rooms import require_room, get_room_snapshot
from fastapi import APIRouter, Request, Depends


router = APIRouter(prefix='/api/rooms/{room_id}/plan')


@router.post('/confirm')
async def confirm(room_id: str, body: Confirm, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        record_confirmation(room, user['id'], body.target.model_dump(), 'confirm')
        finalized = finalize_plan(room)
        records = {'room:' + room_id:room}
        if finalized:
            history = db.get('confirmed-history:' + room_id) or []
            records['confirmed-history:' + room_id] = history + [room['confirmed_plan']]
        db.put_many(records)
        publish_event(db, room_id, 'room.updated', {'changed':['review_plan','active_target','confirmations']})
        if finalized:
            publish_event(db, room_id, 'plan.confirmed', {'target':room['active_target']})
        room = require_room(db, room_id, user['id'])
    return get_room_snapshot(request.app.state.db, room_id, user['id'])

@router.post('/withdraw')
async def withdraw(room_id: str, body: Confirm, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        record_confirmation(room, user['id'], body.target.model_dump(), 'withdraw')
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['confirmations']})
    return get_room_snapshot(request.app.state.db, room_id, user['id'])

@router.post('/activate')
async def activate(room_id: str, body: Activate, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        activate_plan(room, body.plan_revision)
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['review_plan','active_target','confirmations']})
    return get_room_snapshot(request.app.state.db, room_id, user['id'])
