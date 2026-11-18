from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from html import escape
from pathlib import Path


def mount_frontend(app, directory, public_key):
    directory = Path(directory)
    if not (directory / 'index.html').is_file():
        return

    def with_key(name):
        html = (directory / name).read_text(encoding='utf-8')
        return html.replace('<meta name="kakao-map-app-key" content="">', '<meta name="kakao-map-app-key" content="' + escape(public_key, quote=True) + '">')

    @app.get('/', response_class=HTMLResponse)
    @app.get('/index.html', response_class=HTMLResponse)
    async def index():
        return with_key('index.html')

    @app.get('/rooms', response_class=HTMLResponse)
    async def rooms_page():
        return with_key('rooms.html')

    @app.get('/dev')
    async def developer():
        return FileResponse(directory / 'dev.html')

    @app.get('/login')
    async def login_page():
        return FileResponse(directory / 'login.html')

    @app.get('/signup')
    async def signup_page():
        return FileResponse(directory / 'signup.html')

    app.mount('/', StaticFiles(directory=directory, html=True), name='frontend')
