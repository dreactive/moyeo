from fastapi import APIRouter, Request, Depends
from backend.auth import require_user

router = APIRouter(prefix='/api/auth')


def current_user(request: Request):
    return require_user(request.app.state.db, request.cookies.get('session'))


@router.get('/me')
def me(user=Depends(current_user)):
    return user

from fastapi import Response, HTTPException
from pydantic import BaseModel, Field
from backend.auth import register_user, issue_session


class Registration(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


def set_session(response, db, user):
    response.set_cookie('session', issue_session(db, user['id']), httponly=True, samesite='lax')


@router.post('/register', status_code=201)
def register(body: Registration, request: Request, response: Response):
    db = request.app.state.db
    if db.get('email:' + body.email.lower()):
        raise HTTPException(409, 'Email already registered')
    user = register_user(db, body.name, body.email, body.password)
    set_session(response, db, user)
    return user
