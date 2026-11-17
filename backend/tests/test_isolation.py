import importlib.util


def test_backend_boots_without_ai_or_torch():
    assert importlib.util.find_spec("backend.app") is not None


def test_app_closes_injected_port_once():
    from fastapi.testclient import TestClient
    from backend.app import create_app
    class Port:
        closed = 0
        async def aclose(self):
            self.closed += 1
    port = Port()
    with TestClient(create_app(port)) as client:
        assert client.get('/openapi.json').status_code == 200
    assert port.closed == 1


def test_default_fixture_port():
    from backend.app import create_app
    from fastapi.testclient import TestClient
    from backend.adapters.fixture_agent import FixtureAgentPort
    with TestClient(create_app()) as client:
        assert isinstance(client.app.state.agent, FixtureAgentPort)


def test_backend_boots_without_ai_or_torch_in_fresh_process(tmp_path):
    import subprocess
    import sys
    import os
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    program = '''
import importlib.abc
import sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'ai','torch','transformers','frontend'}:
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, Block())
from backend.app import create_app
from fastapi.testclient import TestClient
with TestClient(create_app(database_path=':memory:')) as client:
    assert client.get('/api/auth/me').status_code == 401
    assert client.get('/openapi.json').status_code == 200
'''
    env = dict(os.environ, PYTHONPATH=str(root))
    result = subprocess.run([sys.executable,'-c',program], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_observation_module_can_be_imported_first():
    import subprocess
    import sys
    result = subprocess.run([sys.executable,'-c','import backend.services.observations; import backend.app'], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
