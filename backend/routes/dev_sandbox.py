from backend.dev_auth import require_developer
from backend.dev_examples import tool_examples
from backend.dev_schemas import SearchTool, DetailsTool
from backend.services.dev_sandbox import execute_tool
from fastapi import APIRouter, Body, Depends, Request


router = APIRouter(prefix='/api/dev', tags=['Developer sandbox'], dependencies=[Depends(require_developer)])


@router.post('/tools/search_places', summary='Search places (developer only)')
async def search_places(request: Request, body: SearchTool = Body(openapi_examples=tool_examples('search_places'))):
    return await execute_tool(body, 'search_places', request.app.state.dev_runtime_config)


@router.post('/tools/get_place_details', summary='Get menus, prices and opening hours (developer only)')
async def get_place_details(request: Request, body: DetailsTool = Body(openapi_examples=tool_examples('get_place_details'))):
    return await execute_tool(body, 'get_place_details', request.app.state.dev_runtime_config)
