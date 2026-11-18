from backend.auth import register_user, issue_session, require_user, verify_password, burn_password_check, EmailTaken, SESSION_DAYS
from fastapi import APIRouter, Request, Depends
from fastapi import Response, HTTPException
from pydantic import BaseModel, Field, field_validator
import re

EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


router = APIRouter(prefix='/api/auth')


def current_user(request: Request):
    return require_user(request.app.state.db, request.cookies.get('session'))


@router.get('/me')
def me(user=Depends(current_user)):
    return user



class Registration(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)

    @field_validator('name')
    @classmethod
    def name_not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('name must not be blank')
        return value

    @field_validator('email')
    @classmethod
    def email_format(cls, value):
        value = value.strip().lower()
        if not EMAIL.match(value):
            raise ValueError('invalid email')
        return value

    @field_validator('password')
    @classmethod
    def password_not_blank(cls, value):
        if not value.strip():
            raise ValueError('password must not be blank')
        return value


def set_session(response, db, user, secure=False):
    response.set_cookie('session', issue_session(db, user['id']), httponly=True, samesite='lax', secure=secure, max_age=SESSION_DAYS * 86400)


@router.post('/register', status_code=201)
def register(body: Registration, request: Request, response: Response):
    db = request.app.state.db
    try:
        user = register_user(db, body.name, body.email, body.password)
    except EmailTaken:
        raise HTTPException(409, 'Email already registered')
    set_session(response, db, user, request.app.state.cookie_secure)
    return user

@router.post('/logout')
def logout(request: Request, response: Response):
    token = request.cookies.get('session')
    if token:
        request.app.state.db.put('session:' + token, None)
    response.delete_cookie('session', secure=request.app.state.cookie_secure, httponly=True, samesite='lax')
    return {'ok': True}


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)


@router.post('/login')
def login(body: Login, request: Request, response: Response):
    db = request.app.state.db
    user_id = db.get('email:' + body.email.strip().lower())
    stored = db.get('user:' + user_id) if user_id else None
    valid = verify_password(body.password, stored['password_hash']) if stored else burn_password_check(body.password)
    if not valid:
        raise HTTPException(401, 'Invalid credentials')
    user = {key: stored[key] for key in ('id', 'name', 'email')}
    set_session(response, db, user, request.app.state.cookie_secure)
    return user
