from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlite3 import Error

router = APIRouter()


@router.get('/api/health')
def health(request: Request):
    try:
        request.app.state.db.get('__health__')
    except Error:
        return JSONResponse({'status': 'unavailable'}, status_code=503)
    return {'status': 'ok'}
