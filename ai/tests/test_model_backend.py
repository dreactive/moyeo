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
