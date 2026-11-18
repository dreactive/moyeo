def test_developer_auth_is_available_in_swagger(api):
    schema = api.get('/openapi.json').json()
    operation = schema['paths']['/api/dev/rooms/{room_id}/traces']['get']
    assert operation['security'] == [{'DeveloperToken': []}]
    assert schema['components']['securitySchemes']['DeveloperToken']['name'] == 'X-Dev-Token'


def test_search_example_is_a_valid_editable_request():
    from backend.dev_examples import tool_examples
    from backend.dev_schemas import SearchTool
    body = SearchTool.model_validate(tool_examples('search_places')['fixture']['value'])
    assert body.arguments.query == 'A식당'


def test_direct_tool_execution_uses_the_real_registry(api):
    from backend.dev_examples import tool_examples
    from backend.dev_schemas import SearchTool
    from backend.services.dev_sandbox import execute_tool
    body = SearchTool.model_validate(tool_examples('search_places')['fixture']['value'])
    result = api.portal.call(execute_tool, body, 'search_places', {'provider_mode': 'fixture'})
    assert result['result']['places'][0]['id'] == 'fixture:place-a'


def test_search_tool_has_editable_swagger_inputs(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    response = api.post('/api/dev/tools/search_places', json=tool_examples('search_places')['fixture']['value'],
                        headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 200, response.text
    assert response.json()['result']['places'][0]['id'] == 'fixture:place-a'


def test_place_details_endpoint_returns_observed_prices(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    response = api.post('/api/dev/tools/get_place_details', json=tool_examples('get_place_details')['fixture']['value'],
                        headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 200, response.text
    assert response.json()['result']['menus'][0]['price_krw'] == 10000


def test_car_route_endpoint_preserves_units(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    response = api.post('/api/dev/tools/get_car_route', json=tool_examples('get_car_route')['fixture']['value'],
                        headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 200, response.text
    result = response.json()['result']
    assert (result['distance_m'], result['duration_seconds']) == (4000, 600)


def test_tool_response_context_can_be_reused(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    result = api.post('/api/dev/tools/search_places', json=tool_examples('search_places')['fixture']['value'],
                      headers={'X-Dev-Token': 'test-dev'}).json()
    assert result['context']['observations'][-1] == result['observation']
    assert result['observation']['result'] == result['result']


def test_itinerary_endpoint_derives_canonical_arguments(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    response = api.post('/api/dev/tools/build_itinerary', json=tool_examples('build_itinerary')['fixture']['value'],
                        headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 200, response.text
    assert response.json()['result']['days'][0]['visits'][0]['start_at'].endswith('11:30:00+09:00')


def test_cost_endpoint_preserves_unknown_amounts(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    response = api.post('/api/dev/tools/calculate_costs', json=tool_examples('calculate_costs')['fixture']['value'],
                        headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 200, response.text
    result = response.json()['result']
    assert result['known_total_krw'] == 120000
    assert result['total_krw'] is None and result['unknown_line_count'] == 2


def test_invalid_place_returns_validation_error(api):
    from backend.dev_examples import tool_examples
    api.app.state.dev_token = 'test-dev'
    body = tool_examples('get_place_details')['fixture']['value']
    body['arguments']['place_ref'] = 'unknown'
    response = api.post('/api/dev/tools/get_place_details', json=body, headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 422


def test_provider_failure_does_not_expose_secrets(api, monkeypatch):
    import httpx
    from ai.tools.registry import RegisteredTools
    from backend.dev_examples import tool_examples
    async def fail(*args):
        raise httpx.ConnectError('provider-token=secret')
    monkeypatch.setattr(RegisteredTools, 'execute', fail)
    api.app.state.dev_token = 'test-dev'
    response = api.post('/api/dev/tools/search_places', json=tool_examples('search_places')['fixture']['value'],
                        headers={'X-Dev-Token': 'test-dev'})
    assert response.status_code == 502 and 'secret' not in response.text


def test_developer_agent_is_lazy_and_separate_from_fixture(api):
    bridge = api.app.state.dev_agent
    assert bridge.runtime is None
    assert bridge is not api.app.state.agent


def test_utterance_builds_fresh_isolated_message():
    from backend.dev_schemas import Utterance
    from backend.dev_examples import tool_examples
    from backend.services.dev_sandbox import utterance_task
    body = Utterance(context=tool_examples('search_places')['fixture']['value']['context'], text='예산은 15만원')
    first, second = utterance_task(body), utterance_task(body)
    assert first['run_id'] != second['run_id']
    assert first['recent_messages'][-1]['text'] == body.text
    assert first['recent_messages'][-1]['author_id'] == 'u1'


def test_utterance_rejects_unknown_author():
    import pytest
    from fastapi import HTTPException
    from backend.dev_schemas import Utterance
    from backend.dev_examples import tool_examples
    from backend.services.dev_sandbox import utterance_task
    body = Utterance(context=tool_examples('search_places')['fixture']['value']['context'], text='안녕', author_id='outsider')
    with pytest.raises(HTTPException) as error:
        utterance_task(body)
    assert error.value.status_code == 422


def test_utterance_service_returns_agent_result_and_trace(api):
    from backend.dev_schemas import Utterance
    from backend.dev_examples import tool_examples
    from backend.services.dev_sandbox import run_utterance
    from starlette.requests import Request
    body = Utterance(context=tool_examples('search_places')['fixture']['value']['context'], text='예산은 15만원', goal='extract')
    request = Request({'type': 'http', 'app': api.app})
    result = api.portal.call(run_utterance, request, body)
    assert result['result']['constraint_proposals']
    assert result['trace'][0]['event'] == 'decision'
