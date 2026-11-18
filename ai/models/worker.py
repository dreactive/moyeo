from threading import RLock


class ModelWorker:
    def __init__(self, backend):
        self.backend, self.lock, self.closed = backend, RLock(), False
        self.mode = getattr(backend, "mode", "unknown")

    def call(self, method, *args):
        with self.lock:
            if self.closed:
                raise RuntimeError("Model worker closed")
            return getattr(self.backend, method)(*args)

    def generate_json(self, request):
        return self.call("generate_json", request)

    def score_candidates(self, context: dict, candidates: list[dict]) -> list[float]:
        return self.call("score_candidates", context, candidates)

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                if hasattr(self.backend, "close"):
                    self.backend.close()
