"""Read-only developer calls; results never enter the room application pipeline."""
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import HTTPException


async def execute_tool(body, name, settings):
    async with sandbox_errors():
        return await tool_result(body, name, settings)


@asynccontextmanager
async def sandbox_errors():
    try:
        yield
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError) as error:
        raise HTTPException(422, {'error': type(error).__name__, 'message': 'Invalid sandbox arguments or context'}) from None


async def tool_result(body, name, settings):
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(body.context.model_dump(), settings.get('provider_mode', 'fixture'), settings)
    if body.arguments is None:
        from ai.planning import itinerary_arguments
        from ai.cost_inputs import build_cost_inputs
        arguments = build_cost_inputs(tools.context)[0] if name == 'calculate_costs' else itinerary_arguments(tools.context)
    else:
        arguments = body.arguments.model_dump()
    result = await tools.execute(name, arguments)
    context = body.context.model_dump()
    observation = dict(tool_name=name, arguments=arguments, result=result,
                       observed_at=datetime.now(timezone.utc).isoformat(),
                       source_refs=[e['id'] for e in result.get('evidence', [])])
    if result.get('evidence_id'):
        observation['source_refs'].append(result['evidence_id'])
    context['observations'].append(observation)
    return dict(tool_name=name, provider_mode=tools.mode, arguments=arguments, result=result,
                observation=observation, context=context)
