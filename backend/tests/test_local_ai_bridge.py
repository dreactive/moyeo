import asyncio
import sys
import types


def test_bridge_is_lazy_and_preserves_json_and_closes_once(monkeypatch):
    from backend.adapters.local_ai import LocalAIBridge
    calls = []
    class Runtime:
        async def run(self, task, emit):
            return task
        async def execute_tool(self, name, args, context):
            return {'name':name,'arguments':args,'context':context}
        async def aclose(self):
            calls.append('closed')
    module = types.ModuleType('ai.runtime')
    module.create_runtime = lambda config: calls.append(config) or Runtime()
    monkeypatch.setitem(sys.modules,'ai.runtime',module)
    bridge = LocalAIBridge({'model_backend':'fake','provider_mode':'fixture'})
    assert calls == []
    async def scenario():
        await bridge.start()
        await bridge.start()
        assert await bridge.run({'room_id':'r'}, None) == {'room_id':'r'}
        assert (await bridge.execute_tool('x', {}, {'room_id':'r'}))['context']['room_id'] == 'r'
        await bridge.aclose()
        await bridge.aclose()
    asyncio.run(scenario())
    assert len(calls) == 2


def test_bridge_is_started_by_app_lifespan(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app import create_app
    from backend.adapters.local_ai import LocalAIBridge
    calls = []
    module = types.ModuleType('ai.runtime')
    class Runtime:
        async def aclose(self):
            calls.append('closed')
    module.create_runtime = lambda config: calls.append(config) or Runtime()
    monkeypatch.setitem(sys.modules,'ai.runtime',module)
    with TestClient(create_app(LocalAIBridge({'model_backend':'fake'}), database_path=':memory:')):
        assert len(calls) == 1
    assert calls[-1] == 'closed'


def test_failed_live_runtime_is_not_fixture_success(monkeypatch):
    import pytest
    from fastapi.testclient import TestClient
    from backend.app import create_app
    from backend.adapters.local_ai import LocalAIBridge
    module = types.ModuleType('ai.runtime')
    def fail(config):
        raise RuntimeError('Live runtime unavailable')
    module.create_runtime = fail
    monkeypatch.setitem(sys.modules,'ai.runtime',module)
    with pytest.raises(RuntimeError, match='Live runtime unavailable'):
        with TestClient(create_app(LocalAIBridge({'provider_mode':'live'}), database_path=':memory:')):
            pass


def test_bridge_forwards_current_snapshot_callback_without_changing_legacy_run(monkeypatch):
    from backend.adapters.local_ai import LocalAIBridge
    checks = []
    class Runtime:
        async def run(self, task, emit, **kwargs):
            checks.append(kwargs)
            return {'current': kwargs['is_current']()} if kwargs else task
    module = types.ModuleType('ai.runtime')
    module.create_runtime = lambda config: Runtime()
    monkeypatch.setitem(sys.modules, 'ai.runtime', module)
    bridge = LocalAIBridge({})
    async def scenario():
        await bridge.start()
        guard = lambda: False
        assert await bridge.run_current({'room_id': 'r'}, None, guard) == {'current': False}
        assert await bridge.run({'room_id': 'r'}, None) == {'room_id': 'r'}
        assert checks == [{'is_current': guard}, {}]
    asyncio.run(scenario())
