"""Read-only developer calls; results never enter the room application pipeline."""
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import HTTPException
from httpx import HTTPError
from uuid import uuid4
from backend.services.traces import sanitize
from decimal import DecimalException
import httpx
import asyncio


async def execute_tool(body, name, settings):
    async with sandbox_errors():
        validate_settings(settings)
        return await tool_result(body, name, settings)


def validate_settings(settings):
    if (settings.get('provider_mode', 'fixture') not in ('fixture', 'live')
            or settings.get('model_backend', 'fake') not in ('fake', 'local_qwen')):
        raise HTTPException(503, 'Invalid server model/provider configuration')


PROVIDER_KEYS = {'search_places': ('KAKAO_REST_API_KEY',), 'get_place_details': ('APIFY_TOKEN',),
                 'get_car_route': ('KAKAO_MOBILITY_API_KEY', 'KAKAO_REST_API_KEY')}


def require_provider_credentials(mode, credentials, name):
    if mode == 'live' and name in PROVIDER_KEYS and not any(credentials.get(key) for key in PROVIDER_KEYS[name]):
        raise HTTPException(503, 'Provider credentials unavailable; check server configuration')


@asynccontextmanager
async def sandbox_errors():
    try:
        yield
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, DecimalException) as error:
        raise HTTPException(422, {'error': type(error).__name__, 'message': 'Invalid sandbox arguments or context'}) from None
    except HTTPError:
        raise HTTPException(502, 'Provider request failed; check server configuration and connectivity') from None
    except (ImportError, OSError, RuntimeError):
        raise HTTPException(503, 'AI runtime unavailable; check server dependencies and configuration') from None


async def tool_result(body, name, settings):
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(body.context.model_dump(), settings.get('provider_mode', 'fixture'), settings)
    require_provider_credentials(tools.mode, tools.credentials, name)
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


def utterance_task(body):
    task = body.context.model_dump()
    if body.author_id not in {member['user_id'] for member in task['members']}:
        raise HTTPException(422, 'author_id must belong to context.members')
    task.update(run_id=uuid4().hex, goal=body.goal)
    task['recent_messages'].append(dict(id=uuid4().hex, author_id=body.author_id,
                                        text=body.text, created_at=datetime.now(timezone.utc).isoformat()))
    return task


async def run_utterance(request, body):
    async with sandbox_errors():
        validate_settings(request.app.state.dev_runtime_config)
        task, trace = utterance_task(body), []
        async def capture(event):
            trace.append(sanitize(event))
        bridge = await start_agent(request)
        result = await bridge.run(task, capture)
        raise_termination_error(trace)
        settings = request.app.state.dev_runtime_config
        return dict(model_backend=settings.get('model_backend', 'fake'),
                    provider_mode=settings.get('provider_mode', 'fixture'), result=result, trace=trace)


def raise_termination_error(trace):
    for event in trace:
        reason = event.get('payload', {}).get('termination', '')
        error_type = getattr(httpx, reason, None)
        if isinstance(error_type, type) and issubclass(error_type, HTTPError):
            raise HTTPException(502, 'Agent provider request failed')
        if reason in ('RuntimeError', 'OSError'):
            raise HTTPException(503, 'Agent runtime failed')
        if reason in ('ValueError', 'KeyError', 'TypeError'):
            raise HTTPException(422, 'Agent could not process sandbox arguments or context')


def load_dev_runtime(config):
    from ai.runtime import create_runtime
    return create_runtime(config)


async def start_agent(request):
    bridge = request.app.state.dev_agent
    async with request.app.state.dev_agent_lock:
        if bridge.runtime is None:
            try:
                bridge.runtime = await asyncio.to_thread(load_dev_runtime, bridge.config)
            except ValueError:
                raise HTTPException(503, 'Invalid local model configuration') from None
    return bridge
