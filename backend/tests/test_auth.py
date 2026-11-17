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
