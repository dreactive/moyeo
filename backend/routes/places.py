from fastapi import APIRouter, Request, Depends, HTTPException
from backend.routes.auth import current_user
from backend.services.rooms import require_room
from backend.services.observations import observed_place

router = APIRouter(prefix='/api/rooms/{room_id}/places')


@router.get('/{place_ref}')
async def details(room_id: str, place_ref: str, request: Request, user=Depends(current_user)):
    require_room(request.app.state.db, room_id, user['id'])
    result = observed_place(request.app.state.db, room_id, place_ref)
    if result is None:
        raise HTTPException(404, 'Place not observed in this room')
    return result
