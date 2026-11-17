from pathlib import Path
from html import escape
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app, directory, public_key):
    directory = Path(directory)
    if not (directory / 'index.html').is_file():
        return

    @app.get('/', response_class=HTMLResponse)
    @app.get('/index.html', response_class=HTMLResponse)
    async def index():
        html = (directory / 'index.html').read_text(encoding='utf-8')
        return html.replace('<meta name="kakao-map-app-key" content="">', '<meta name="kakao-map-app-key" content="' + escape(public_key, quote=True) + '">')

    @app.get('/dev')
    async def developer():
        return FileResponse(directory / 'dev.html')

    app.mount('/', StaticFiles(directory=directory, html=True), name='frontend')
