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


def test_worker_records_state_applied_without_user_trace(api):
    api.app.state.dev_token = 'test-dev'
    receipt = api.post('/api/rooms/room-fixture/agent-runs', json={'reason':'manual_replan'}).json()
    api.portal.call(api.app.state.jobs.queue.join)
    traces = api.get('/api/dev/rooms/room-fixture/traces', headers={'X-Dev-Token':'test-dev'}).json()['runs']
    assert traces[0]['run_id'] == receipt['run_id']
    assert traces[0]['events'][-1]['event'] == 'state_applied'
    assert traces[0]['events'][-1]['payload']['applied'] is True
    assert 'trace' not in api.get('/api/rooms/room-fixture').text


def test_trace_can_be_disabled_without_losing_product_data(api, agent_result):
    from backend.services.traces import store_trace
    from backend.services.observations import project_observations, observed_place
    db = api.app.state.db
    db.trace_enabled = False
    db.put('run:r', {'room_id':'room-fixture'})
    event = dict(run_id='r',step=1,event='decision',call_id=None,created_at='2026-11-18T10:00:00+09:00',payload={})
    assert not store_trace(db, event)
    project_observations(db, 'room-fixture', agent_result['observations'])
    assert observed_place(db, 'room-fixture', 'fixture:place-a') is not None
    assert db.traces == {}
