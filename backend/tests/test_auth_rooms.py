from fastapi.testclient import TestClient
from backend.app import create_app


def test_cookie_identity_register_and_me():
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.get('/api/auth/me').status_code == 401
        response = client.post('/api/auth/register', json={'name':'민수','email':'a@example.test','password':'password123'})
        assert response.status_code == 201
        assert client.get('/api/auth/me').json() == response.json()
        assert 'httponly' in response.headers['set-cookie'].lower()
