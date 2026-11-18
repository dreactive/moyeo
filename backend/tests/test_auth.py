def test_password_hash_is_salted():
    from backend.auth import hash_password, verify_password
    first = hash_password('correct horse')
    assert first != hash_password('correct horse')
    assert verify_password('correct horse', first)
    assert not verify_password('wrong', first)


def test_account_registration_hides_hash():
    from backend.auth import register_user
    from backend.db import Database
    db = Database(':memory:')
    user = register_user(db, '민수', 'a@example.test', 'password123')
    assert set(user) == {'id', 'name', 'email'}
    assert db.get('user:' + user['id'])['password_hash'] != 'password123'


def test_sessions_are_opaque_and_resolve_user():
    from backend.auth import issue_session, require_user, register_user
    from backend.db import Database
    db = Database(':memory:')
    user = register_user(db, 'a', 'a@b.test', 'password123')
    token = issue_session(db, user['id'])
    assert user['id'] not in token
    assert require_user(db, token) == user


def test_me_requires_cookie():
    from backend.app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.get('/api/auth/me').status_code == 401


def test_registration_normalizes_and_rejects_invalid_input():
    from backend.app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(database_path=':memory:')) as client:
        created = client.post('/api/auth/register', json={'name':' 민수 ','email':' A@Example.Test ','password':'password123'})
        assert created.status_code == 201
        assert created.json()['name'] == '민수' and created.json()['email'] == 'a@example.test'
        assert client.post('/api/auth/register', json={'name':'b','email':'a@example.test','password':'password123'}).status_code == 409
        for body in ({'name':'   ','email':'b@example.test','password':'password123'},
                     {'name':'b','email':'not-an-email','password':'password123'},
                     {'name':'b','email':'b@example.test','password':'        '},
                     {'name':'b','email':'b@example.test','password':'short'},
                     {'name':'b','email':'b@example.test','password':'x' * 257}):
            assert client.post('/api/auth/register', json=body).status_code == 422, body
        client.post('/api/auth/logout')
        assert client.post('/api/auth/login', json={'email':' A@EXAMPLE.TEST','password':'password123'}).status_code == 200


def test_duplicate_registration_is_atomic():
    from backend.auth import register_user, EmailTaken
    from backend.db import Database
    from concurrent.futures import ThreadPoolExecutor
    db = Database(':memory:')
    def attempt(index):
        try:
            return register_user(db, str(index), 'same@example.test', 'password123')
        except EmailTaken:
            return None
    with ThreadPoolExecutor(8) as pool:
        created = [user for user in pool.map(attempt, range(8)) if user]
    assert len(created) == 1
    assert db.get('email:same@example.test') == created[0]['id']


def test_sessions_expire_and_cookie_has_lifetime():
    from datetime import datetime, timedelta, timezone
    from backend.auth import issue_session, session_user_id, register_user, SESSION_DAYS
    from backend.db import Database
    db = Database(':memory:')
    user = register_user(db, 'a', 'a@b.test', 'password123')
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token = issue_session(db, user['id'], now=start)
    assert session_user_id(db, token, now=start + timedelta(days=SESSION_DAYS - 1)) == user['id']
    assert session_user_id(db, token, now=start + timedelta(days=SESSION_DAYS)) is None
    assert session_user_id(db, token, now=start) is None
    from backend.app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(database_path=':memory:')) as client:
        cookie = client.post('/api/auth/register', json={'name':'a','email':'a@b.test','password':'password123'}).headers['set-cookie'].lower()
        assert 'max-age=' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie


def test_logout_without_cookie_writes_nothing():
    from backend.app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.post('/api/auth/logout').status_code == 200
        assert client.app.state.db.get('session:') is None
