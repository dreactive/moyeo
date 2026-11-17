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
