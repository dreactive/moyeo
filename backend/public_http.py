from collections import deque
from time import monotonic
from fastapi.responses import JSONResponse


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
    budget = RequestBudget(settings.get('public_requests_per_minute', 60))
    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        return JSONResponse({'detail': 'Internal server error'}, status_code=500, headers={'Cache-Control': 'no-store'})

    @app.middleware('http')
    async def public_http(request, call_next):
        is_api = request.url.path == '/api' or request.url.path.startswith('/api/')
        if is_api and request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and not budget.allow(monotonic()):
            response = JSONResponse({'detail': 'Request limit reached; retry later'}, status_code=429, headers={'Retry-After': '60'})
        else:
            response = await call_next(request)
        if is_api:
            response.headers['Cache-Control'] = 'no-store'
        return response
