from backend.auth import register_user, issue_session
from backend.auth import require_user
from fastapi import APIRouter, Request, Depends
from fastapi import Response, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix='/api/auth')


def current_user(request: Request):
    return require_user(request.app.state.db, request.cookies.get('session'))


@router.get('/me')
def me(user=Depends(current_user)):
    return user



class Registration(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)


def set_session(response, db, user, secure=False):
    response.set_cookie('session', issue_session(db, user['id']), httponly=True, samesite='lax', secure=secure)


@router.post('/register', status_code=201)
def register(body: Registration, request: Request, response: Response):
    db = request.app.state.db
    if db.get('email:' + body.email.lower()):
        raise HTTPException(409, 'Email already registered')
    user = register_user(db, body.name, body.email, body.password)
    set_session(response, db, user, request.app.state.cookie_secure)
    return user

@router.post('/logout')
def logout(request: Request, response: Response):
    request.app.state.db.put('session:' + request.cookies.get('session', ''), None)
    response.delete_cookie('session', secure=request.app.state.cookie_secure, httponly=True, samesite='lax')
    return {'ok': True}


class Login(BaseModel):
    email: str
    password: str


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    from backend.auth import verify_password
    db = request.app.state.db
    user_id = db.get('email:' + body.email.lower())
    stored = db.get('user:' + user_id) if user_id else None
    if stored is None or not verify_password(body.password, stored['password_hash']):
        raise HTTPException(401, 'Invalid credentials')
    user = {key: stored[key] for key in ('id', 'name', 'email')}
    set_session(response, db, user, request.app.state.cookie_secure)
    return user
