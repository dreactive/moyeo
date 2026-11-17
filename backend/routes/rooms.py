from fastapi import APIRouter, Request, Depends
from backend.routes.auth import current_user
from backend.schemas import CreateRoom
from backend.services.rooms import new_room, require_room, get_room_snapshot
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
    return get_room_snapshot(request.app.state.db, room_id, user['id'])

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
    return get_room_snapshot(request.app.state.db, room_id, user['id'])
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

from backend.schemas import ValueAnswer
from backend.services.consensus import edit_constraint, confirm_constraint


@router.patch('/{room_id}/constraints/{constraint_id}')
async def edit_condition(room_id: str, constraint_id: str, body: ValueAnswer, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        condition = edit_constraint(room, constraint_id, user['id'], body.value)
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['constraints']})
    return condition


@router.post('/{room_id}/constraints/{constraint_id}/confirm')
async def confirm_condition(room_id: str, constraint_id: str, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        confirm_constraint(room, constraint_id, user['id'])
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['constraints','versions','confirmations']})
    await request.app.state.jobs.enqueue(room_id, 'constraint_confirmed')
    return snapshot(room_id, request, user)

from backend.services.questions import answer_question


@router.post('/{room_id}/questions/{question_id}/answer')
async def answer(room_id: str, question_id: str, body: ValueAnswer, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        answer_question(room, question_id, user['id'], body.value)
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['questions','config','constraints','versions','confirmations']})
    await request.app.state.jobs.enqueue(room_id, 'question_answered')
    return snapshot(room_id, request, user)

from backend.schemas import SelectOption
from backend.services.planning import select_conflict_option, apply_selected_condition, validate_effect
from backend.services.observations import get_observations


@router.post('/{room_id}/conflicts/{conflict_id}/select', status_code=202)
async def select_conflict(room_id: str, conflict_id: str, body: SelectOption, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        selection = select_conflict_option(room, conflict_id, body.option_id, user['id'])
        validate_effect(room, selection['effect'], get_observations(db, room_id))
        if selection['effect']['kind'] == 'change_constraint':
            apply_selected_condition(room, selection, user['id'])
            db.put('room:' + room_id, room)
            publish_event(db, room_id, 'room.updated', {'changed':['constraints']})
            selection = None
    return await request.app.state.jobs.enqueue(room_id, 'conflict_selected', selection)
