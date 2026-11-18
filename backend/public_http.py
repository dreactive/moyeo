def configure_public_http(app, settings):
    @app.middleware('http')
    async def public_http(request, call_next):
        response = await call_next(request)
        if request.url.path == '/api' or request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response
