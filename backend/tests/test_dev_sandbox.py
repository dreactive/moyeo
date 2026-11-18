def test_developer_auth_is_available_in_swagger(api):
    schema = api.get('/openapi.json').json()
    operation = schema['paths']['/api/dev/rooms/{room_id}/traces']['get']
    assert operation['security'] == [{'DeveloperToken': []}]
    assert schema['components']['securitySchemes']['DeveloperToken']['name'] == 'X-Dev-Token'
