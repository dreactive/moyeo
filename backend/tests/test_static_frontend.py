from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import read_settings


def test_static_frontend_mount_preserves_api_and_injects_only_public_key(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'index.html').write_text('<meta name="kakao-map-app-key" content="">', encoding='utf-8')
    (tmp_path / 'dev.html').write_text('developer view', encoding='utf-8')
    (tmp_path / 'src' / 'a.js').write_text('export const a=1;', encoding='utf-8')
    settings = read_settings()
    settings['public_map_key'] = 'public-map'
    with TestClient(create_app(database_path=':memory:', settings=settings, frontend_path=tmp_path)) as client:
        assert 'content="public-map"' in client.get('/').text
        assert client.get('/src/a.js').status_code == 200
        assert client.get('/dev').status_code == 200
        assert client.get('/api/auth/me').status_code == 401
