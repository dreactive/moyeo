from backend.dev_auth import require_developer
from backend.services.rooms import require_room
from backend.services.traces import get_run_traces
from fastapi import APIRouter, Request, Depends


router = APIRouter(prefix='/api/dev/rooms')


@router.get('/{room_id}/traces')
async def traces(room_id: str, request: Request, run_id: str | None = None, user=Depends(require_developer)):
    require_room(request.app.state.db, room_id, user['id'])
    return {'runs':get_run_traces(request.app.state.db, room_id, run_id)}
