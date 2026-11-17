from fastapi import APIRouter, Request, Depends, HTTPException
from backend.routes.auth import current_user
from backend.schemas import TextMessage, AgentRun
from backend.services.rooms import require_room
from backend.services.messages import save_message

router = APIRouter(prefix='/api/rooms/{room_id}')


@router.post('/messages', status_code=201)
async def send(room_id: str, body: TextMessage, request: Request, user=Depends(current_user)):
    require_room(request.app.state.db, room_id, user['id'])
    message = save_message(request.app.state.db, room_id, user['id'], body.text)
    await request.app.state.jobs.enqueue(room_id, 'new_message')
    return message


@router.get('/messages')
async def messages(room_id: str, request: Request, after_seq: int=0, user=Depends(current_user)):
    room = require_room(request.app.state.db, room_id, user['id'])
    return {'messages':[message for message in room['messages'] if message['seq']>after_seq], 'last_seq':len(room['messages'])}

@router.get('/messages/{message_id}')
async def evidence(room_id: str, message_id: str, request: Request, user=Depends(current_user)):
    room = require_room(request.app.state.db, room_id, user['id'])
    for message in room['messages']:
        if message['id'] == message_id:
            return message
    raise HTTPException(404, 'Message not found')


@router.post('/agent-runs', status_code=202)
async def agent_run(room_id: str, body: AgentRun, request: Request, user=Depends(current_user)):
    require_room(request.app.state.db, room_id, user['id'])
    return await request.app.state.jobs.enqueue(room_id, body.reason)
