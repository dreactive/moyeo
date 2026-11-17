from backend.routes.auth import current_user
from backend.services.rooms import require_room
from backend.services.traces import get_run_traces
from fastapi import APIRouter, Request, Header, Depends, HTTPException
import hmac


router = APIRouter(prefix='/api/dev/rooms')


@router.get('/{room_id}/traces')
async def traces(room_id: str, request: Request, run_id: str | None = None, x_dev_token: str = Header(''), user=Depends(current_user)):
    expected = request.app.state.dev_token
    if not expected or not hmac.compare_digest(expected, x_dev_token):
        raise HTTPException(403, 'Developer token required')
    require_room(request.app.state.db, room_id, user['id'])
    return {'runs':get_run_traces(request.app.state.db, room_id, run_id)}
