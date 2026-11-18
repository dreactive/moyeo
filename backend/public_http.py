from collections import deque


class RequestBudget:
    def __init__(self, limit):
        if limit < 0:
            raise ValueError('Request limit must be nonnegative')
        self.limit = limit
        self.times = deque()

    def allow(self, now):
        while self.times and self.times[0] <= now - 60:
            self.times.popleft()
        if self.limit and len(self.times) >= self.limit:
            return False
        if self.limit:
            self.times.append(now)
        return True


def configure_public_http(app, settings):
    @app.middleware('http')
    async def public_http(request, call_next):
        response = await call_next(request)
        if request.url.path == '/api' or request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
