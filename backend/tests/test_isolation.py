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
