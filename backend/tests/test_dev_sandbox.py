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
