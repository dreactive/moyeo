import hashlib
import secrets
import hmac


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
