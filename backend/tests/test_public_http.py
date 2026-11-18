from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import read_settings


def test_secure_cookie_setting(monkeypatch):
    monkeypatch.setenv('COOKIE_SECURE', '1')
    with TestClient(create_app(database_path=':memory:'), base_url='https://testserver') as client:
        response = client.post('/api/auth/register', json=dict(name='A', email='a@b.test', password='password123'))
        assert '; Secure' in response.headers['set-cookie']
        assert client.get('/api/auth/me').status_code == 200


def test_api_errors_are_not_cached():
    with TestClient(create_app(database_path=':memory:')) as client:
        response = client.get('/api/auth/me')
        assert response.status_code == 401
        assert response.headers['cache-control'] == 'no-store'
