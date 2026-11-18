from backend.routes.auth import current_user
from backend.services.observations import fetch_place
from backend.services.rooms import require_room
from fastapi import APIRouter, Request, Depends


router = APIRouter(prefix='/api/rooms/{room_id}/places')


@router.get('/{place_ref}')
async def details(room_id: str, place_ref: str, request: Request, location_only: bool = False, user=Depends(current_user)):
    room = require_room(request.app.state.db, room_id, user['id'])
    return await fetch_place(request.app.state.db, request.app.state.agent, room, place_ref, location_only=location_only)
