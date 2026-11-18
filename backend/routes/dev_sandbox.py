from backend.dev_auth import require_developer
from backend.dev_examples import tool_examples
from backend.dev_schemas import SearchTool
from backend.services.dev_sandbox import execute_tool
from fastapi import APIRouter, Body, Depends, Request


router = APIRouter(prefix='/api/dev', tags=['Developer sandbox'], dependencies=[Depends(require_developer)])


@router.post('/tools/search_places', summary='Search places (developer only)')
async def search_places(request: Request, body: SearchTool = Body(openapi_examples=tool_examples('search_places'))):
    return await execute_tool(body, 'search_places', request.app.state.dev_runtime_config)
