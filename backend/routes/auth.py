from fastapi import APIRouter, Request, Depends
from backend.auth import require_user

router = APIRouter(prefix='/api/auth')


def current_user(request: Request):
    return require_user(request.app.state.db, request.cookies.get('session'))


@router.get('/me')
def me(user=Depends(current_user)):
    return user
