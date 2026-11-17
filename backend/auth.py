import hashlib
import hmac
import secrets


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest


def verify_password(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(':')[0]), stored)


def register_user(db, name, email, password):
    user = {'id': secrets.token_hex(16), 'name': name, 'email': email.lower()}
    db.put('user:' + user['id'], dict(user, password_hash=hash_password(password)))
    db.put('email:' + email.lower(), user['id'])
    return user


def issue_session(db, user_id):
    token = secrets.token_urlsafe(32)
    db.put('session:' + token, user_id)
    return token


def require_user(db, token):
    from fastapi import HTTPException
    user_id = db.get('session:' + (token or ''))
    user = db.get('user:' + user_id) if user_id else None
    if user is None:
        raise HTTPException(401, 'Login required')
    return {key: user[key] for key in ('id', 'name', 'email')}
