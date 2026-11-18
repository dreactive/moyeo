import hmac
from backend.routes.auth import current_user
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader


developer_token = APIKeyHeader(name='X-Dev-Token', scheme_name='DeveloperToken', auto_error=False)


def require_developer(request: Request, token: str | None = Security(developer_token), user=Depends(current_user)):
    expected = request.app.state.dev_token
    if not expected or not token or not hmac.compare_digest(expected.encode(), token.encode()):
        raise HTTPException(403, 'Developer token required')
    return user
