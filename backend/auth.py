from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

SESSION_DAYS = 30
_DUMMY_HASH = None


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + digest


def verify_password(password, stored):
    return hmac.compare_digest(hash_password(password, stored.split(':')[0]), stored)


def burn_password_check(password):
    """Spend the same hashing time for an unknown email so login timing does not reveal accounts."""
    global _DUMMY_HASH
    _DUMMY_HASH = _DUMMY_HASH or hash_password(secrets.token_hex(8))
    verify_password(password, _DUMMY_HASH)
    return False


class EmailTaken(Exception):
    pass


def register_user(db, name, email, password):
    email = email.strip().lower()
    user = {'id': secrets.token_hex(16), 'name': name.strip(), 'email': email}
    password_hash = hash_password(password)
    with db.lock:
        if db.get('email:' + email):
            raise EmailTaken(email)
        db.put_many({'user:' + user['id']: dict(user, password_hash=password_hash), 'email:' + email: user['id']})
    return user


def issue_session(db, user_id, now=None):
    token = secrets.token_urlsafe(32)
    expires_at = (now or datetime.now(timezone.utc)) + timedelta(days=SESSION_DAYS)
    db.put('session:' + token, {'user_id': user_id, 'expires_at': expires_at.isoformat()})
    return token


def session_user_id(db, token, now=None):
    if not token:
        return None
    record = db.get('session:' + token)
    if isinstance(record, str):
        return record
    if not isinstance(record, dict):
        return None
    if datetime.fromisoformat(record['expires_at']) <= (now or datetime.now(timezone.utc)):
        db.put('session:' + token, None)
        return None
    return record['user_id']


def require_user(db, token):
    from fastapi import HTTPException
    user_id = session_user_id(db, token)
    user = db.get('user:' + user_id) if user_id else None
    if user is None:
        raise HTTPException(401, 'Login required')
    return {key: user[key] for key in ('id', 'name', 'email')}
