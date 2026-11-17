import importlib.util


def test_backend_boots_without_ai_or_torch():
    assert importlib.util.find_spec("backend.app") is not None
