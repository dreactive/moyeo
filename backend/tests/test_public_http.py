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


def test_request_budget_recovers_after_a_minute():
    from backend.public_http import RequestBudget
    budget = RequestBudget(1)
    assert budget.allow(0)
    assert not budget.allow(59)
    assert budget.allow(60)


def test_mutation_limit_rejects_before_handler_and_allows_reads(tmp_path):
    settings = dict(read_settings(), public_requests_per_minute=1)
    app = create_app(database_path=':memory:', settings=settings, frontend_path=tmp_path)
    calls = []
    @app.post('/api/probe')
    def probe():
        calls.append(1)
        return {'ok': True}
    with TestClient(app) as client:
        assert client.post('/api/probe').status_code == 200
        limited = client.post('/api/probe')
        assert limited.status_code == 429
        assert limited.headers['retry-after'] == '60'
        assert limited.headers['cache-control'] == 'no-store'
        assert len(calls) == 1
        assert client.get('/api/auth/me').status_code == 401


def test_health_reports_database_availability_only():
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.get('/api/health').json() == {'status': 'ok'}
        client.app.state.db.close()
        response = client.get('/api/health')
        assert response.status_code == 503
        assert response.json() == {'status': 'unavailable'}
