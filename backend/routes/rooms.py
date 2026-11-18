from backend.routes.auth import current_user
from backend.schemas import CreateRoom
from backend.schemas import JoinRoom, InviteMember
from backend.schemas import SelectOption
from backend.schemas import TripConfig
from backend.schemas import ValueAnswer
from backend.services.consensus import edit_constraint, confirm_constraint
from backend.services.events import publish_event
from backend.services.observations import get_observations
from backend.services.planning import select_conflict_option, apply_selected_condition, validate_effect
from backend.services.questions import answer_question
from backend.services.rooms import new_room, require_room, get_room_snapshot, list_rooms, add_member, delete_room, room_owner_id
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends
from fastapi import HTTPException
from pydantic import ValidationError
import secrets


router = APIRouter(prefix='/api/rooms')


@router.get('')
def my_rooms(request: Request, user=Depends(current_user)):
    return {'rooms': list_rooms(request.app.state.db, user['id'])}


@router.post('', status_code=201)
def create(body: CreateRoom, request: Request, user=Depends(current_user)):
    title = body.title.strip() if body.title and body.title.strip() else user['name'] + '의 여행방'
    config = body.model_dump(exclude={'title'})  # city stays empty until the owner picks it
    room = new_room(user, dict(config, title=title))
    room.update(room_id=secrets.token_hex(16), invite_code=secrets.token_urlsafe(6), title=title, owner_id=user['id'], config=config, agent_status={'run_id':None,'state':'idle','label':'대기'}, created_at=datetime.now(timezone.utc).isoformat())
    db = request.app.state.db
    db.put('room:' + room['room_id'], room)
    db.put('invite:' + room['invite_code'], room['room_id'])
    return room


@router.get('/{room_id}')
def snapshot(room_id: str, request: Request, user=Depends(current_user)):
    room = require_room(request.app.state.db, room_id, user['id'])
    return get_room_snapshot(request.app.state.db, room_id, user['id'])



@router.delete('/{room_id}')
def remove(room_id: str, request: Request, user=Depends(current_user)):
    delete_room(request.app.state.db, room_id, user['id'])
    return {'ok': True}


@router.post('/join')
def join(body: JoinRoom, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    room_id = db.get('invite:' + body.invite_code)
    if room_id is None:
        raise HTTPException(404, 'Invite not found')
    add_member(db, room_id, user)
    return get_room_snapshot(request.app.state.db, room_id, user['id'])


@router.post('/{room_id}/members', status_code=201)
def invite_member(room_id: str, body: InviteMember, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    require_room(db, room_id, user['id'])
    invited_id = db.get('email:' + body.email.strip().lower())
    invited = db.get('user:' + invited_id) if invited_id else None
    if invited is None:
        raise HTTPException(404, 'User not found')
    added = add_member(db, room_id, invited)
    return {'user_id': invited['id'], 'name': invited['name'], 'added': added}


@router.patch('/{room_id}/trip')
async def trip(room_id: str, body: dict, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    body = dict(body)
    title = body.pop('title', None)
    if title is not None and (not isinstance(title, str) or not title.strip() or len(title.strip()) > 200):
        raise HTTPException(422, 'Invalid room title')
    config_changed = False
    with db.lock:
        room = require_room(db, room_id, user['id'])
        if title is not None and title.strip() != room['title'] and room_owner_id(room) != user['id']:
            raise HTTPException(403, 'Only the room owner may rename')
        try:
            config = TripConfig.model_validate(dict(room['config'], **body)).model_dump()
        except ValidationError:
            raise HTTPException(422, 'Invalid trip configuration')
        changed = []
        if title is not None and title.strip() != room['title']:
            room['title'] = title.strip()
            changed.append('title')
        if config != room['config']:
            room['config'] = config
            room['versions']['constraint_version'] += 1
            room.update(active_target=None, review_plan=None, confirmations=[])
            changed += ['config', 'versions', 'confirmations']
            config_changed = True
        if changed:
            db.put('room:' + room_id, room)
            publish_event(db, room_id, 'room.updated', {'changed': changed})
    if config_changed:
        await request.app.state.jobs.enqueue(room_id, 'trip_changed')
    return snapshot(room_id, request, user)


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



@router.post('/{room_id}/questions/{question_id}/answer')
async def answer(room_id: str, question_id: str, body: ValueAnswer, request: Request, user=Depends(current_user)):
    db = request.app.state.db
    with db.lock:
        room = require_room(db, room_id, user['id'])
        answer_question(room, question_id, user['id'], body.value, get_observations(db, room_id))
        db.put('room:' + room_id, room)
        publish_event(db, room_id, 'room.updated', {'changed':['questions','config','constraints','versions','confirmations']})
    await request.app.state.jobs.enqueue(room_id, 'question_answered')
    return snapshot(room_id, request, user)



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
