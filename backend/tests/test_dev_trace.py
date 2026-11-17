def test_trace_redacts_credentials_and_private_reasoning():
    from backend.services.traces import sanitize
    data = {'api_key':'secret','nested':{'authorization':'Bearer secret','value':3},'reasoning':'private','url':'https://example.test/?api_key=secret&place=a'}
    cleaned = sanitize(data)
    assert 'secret' not in str(cleaned)
    assert 'private' not in str(cleaned)
    assert cleaned['nested']['value'] == 3


def test_trace_storage_links_calls_and_stays_room_scoped():
    from backend.services.traces import store_trace, get_run_traces
    from backend.db import Database
    db = Database(':memory:')
    db.put('run:r', {'room_id':'a'})
    for kind in ('tool_call','tool_result'):
        assert store_trace(db, {'run_id':'r','step':1,'event':kind,'call_id':'call1','created_at':'2026-11-18T10:00:00+09:00','payload':{'tool_name':'get_place_details'}})
    trace = get_run_traces(db, 'a', None)[0]
    assert trace['events'][0]['call_id'] == trace['events'][1]['call_id']
    assert get_run_traces(db, 'b', None) == []


def test_trace_api_requires_developer_token(api):
    api.app.state.dev_token = 'test-dev'
    path = '/api/dev/rooms/room-fixture/traces'
    assert api.get(path).status_code == 403
    assert api.get(path, headers={'X-Dev-Token':'wrong'}).status_code == 403
    response = api.get(path, headers={'X-Dev-Token':'test-dev'})
    assert response.status_code == 200
    assert response.json() == {'runs':[]}
