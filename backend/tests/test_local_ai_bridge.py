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
