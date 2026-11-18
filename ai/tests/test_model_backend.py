import asyncio
import time


async def test_worker_serializes_and_closes_once():
    from ai.models.worker import ModelWorker
    class Backend:
        active = 0
        maximum = 0
        closed = 0
        def generate_json(self, request):
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            time.sleep(.01)
            self.active -= 1
            return request
        def close(self):
            self.closed += 1
    backend = Backend()
    worker = ModelWorker(backend)
    assert await asyncio.gather(*(asyncio.to_thread(worker.generate_json, {"room": r}) for r in range(3))) == [
        {"room": 0}, {"room": 1}, {"room": 2}]
    worker.close()
    worker.close()
    assert backend.maximum == 1 and backend.closed == 1


def test_fake_is_input_based_without_shared_room_cursor():
    from ai.models.fake import FakeModelBackend
    from ai.tests.test_place_route_tools import task
    model = FakeModelBackend()
    request = {"phase": "extract", "context": task()}
    first = model.generate_json(request)
    model.generate_json({"phase": "extract", "context": dict(task(), recent_messages=[])})
    assert model.generate_json(request) == first
    assert first["constraint_proposals"][0]["value"] == 200000
    assert any(s["author_id"] == "u3" and s["item_id"] == "item-b" for s in first["support_observations"])


def test_local_model_missing_paths_fail_without_download():
    import pytest
    from ai.models.qwen_loader import load_components
    with pytest.raises(ValueError, match='local'):
        load_components('missing-base', 'missing-adapter')


def test_model_json_parser_does_not_accept_reasoning_as_data():
    import pytest
    from ai.models.qwen_generation import parse_object
    assert parse_object('```json\n{"candidates": []}\n```') == {"candidates": []}
    with pytest.raises(ValueError):
        parse_object('I think {"price": 10000}')


def test_generation_returns_only_new_tokens(monkeypatch):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace
    from ai.models.qwen_generation import generate_object
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    class Tokens(list):
        shape = (1, 2)
    class Encoding(dict):
        def to(self, device):
            return self
    class Tokenizer:
        eos_token_id = 0
        def apply_chat_template(self, messages, **options):
            return "prompt"
        def __call__(self, text, **options):
            return Encoding(input_ids=Tokens([[8, 9]]))
        def decode(self, ids, **options):
            assert ids == [2, 3]
            return '{"ok": true}'
    model = SimpleNamespace(device="cpu", generate=lambda **options: [[8, 9, 2, 3]])
    assert generate_object(model, Tokenizer(), {"phase": "actions", "context": {}}) == {"ok": True}


def test_base_generation_disables_adapter_and_restores_after_error(monkeypatch):
    from contextlib import contextmanager
    import ai.models.local_qwen as module
    class Model:
        disabled = False
        @contextmanager
        def disable_adapter(self):
            self.disabled = True
            try:
                yield
            finally:
                self.disabled = False
    model = Model()
    monkeypatch.setattr(module, "load_components", lambda *args: (model, object()))
    monkeypatch.setattr(module, "generate_object", lambda m, t, r: {"disabled": m.disabled, "view": r.get("context")})
    backend = module.LocalQwenBackend("base", "adapter")
    assert backend.generate_json({"context": {"polyline": [1], "seconds": 2}}) == {
        "disabled": True, "view": {"seconds": 2}}
    def fail(*args):
        raise ValueError("invalid JSON")
    monkeypatch.setattr(module, "generate_object", fail)
    import pytest
    with pytest.raises(ValueError):
        backend.generate_json({})
    assert not model.disabled

def test_extract_generation_uses_prefix_and_schema_prompt(monkeypatch):
    import sys
    from contextlib import nullcontext
    from types import SimpleNamespace
    import ai.models.qwen_generation as module
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setattr(module, 'extraction_options', lambda request, tokenizer: {'prefix_allowed_tokens_fn': 'filter'})
    class Inputs(dict):
        def to(self, device): return self
    class Tokens(list):
        shape = (1, 1)
    class Tokenizer:
        eos_token_id = 0
        def apply_chat_template(self, messages, **kwargs):
            assert 'places' in messages[0]['content']
            return 'prompt'
        def __call__(self, text, **kwargs): return Inputs(input_ids=Tokens([[9]]))
        def decode(self, tokens, **kwargs): return '{}'
    def generate(**kwargs):
        assert kwargs['prefix_allowed_tokens_fn'] == 'filter'
        return [[9, 0]]
    assert module.generate_object(SimpleNamespace(device='cpu', generate=generate), Tokenizer(), {'phase':'extract','context':{}}) == {}
