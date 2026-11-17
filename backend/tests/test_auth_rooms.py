from fastapi.testclient import TestClient
from backend.app import create_app


def test_cookie_identity_register_and_me():
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.get('/api/auth/me').status_code == 401
        response = client.post('/api/auth/register', json={'name':'민수','email':'a@example.test','password':'password123'})
        assert response.status_code == 201
        assert client.get('/api/auth/me').json() == response.json()
        assert 'httponly' in response.headers['set-cookie'].lower()


def test_login_logout_revokes_cookie():
    with TestClient(create_app(database_path=':memory:')) as client:
        body = {'name': 'a', 'email': 'a@b.test', 'password': 'password123'}
        client.post('/api/auth/register', json=body)
        assert client.post('/api/auth/logout').status_code == 200
        assert client.get('/api/auth/me').status_code == 401
        assert client.post('/api/auth/login', json={'email': body['email'], 'password': 'wrong'}).status_code == 401
        assert client.post('/api/auth/login', json=body).status_code == 200
