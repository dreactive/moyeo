import pytest


@pytest.mark.integration
def test_fake_runtime_applies_json_to_backend(room):
    from backend.adapters.local_ai import LocalAIBridge
    from backend.app import create_app
    from fastapi.testclient import TestClient
    bridge = LocalAIBridge({'model_backend':'fake','provider_mode':'fixture'})
    with TestClient(create_app(bridge, database_path=':memory:')) as client:
        db = client.app.state.db
        db.put('room:room-fixture', room)
        db.put('user:u1', {'id':'u1','name':'Participant 1','email':'u1@example.test'})
        db.put('session:integration-session','u1')
        client.cookies.set('session','integration-session')
        receipt = client.post('/api/rooms/room-fixture/agent-runs', json={'reason':'manual_replan'})
        assert receipt.status_code == 202
        client.portal.call(client.app.state.jobs.queue.join)
        run_id = receipt.json()['run_id']
        assert db.get('run:' + run_id).get('applied') is True
        assert db.observations['room-fixture']
        assert db.get('room:room-fixture')['messages'] == room['messages']
        assert any(event['event'] == 'tool_result' for event in db.traces[run_id]['events'])
        assert db.get('run:' + run_id).get('applied') is True
        assert db.observations.get('room-fixture')
        assert db.get('room:room-fixture')['messages'] == room['messages']
        events = db.traces[run_id]['events']
        assert any(event['event'] == 'decision' and event['payload'].get('model_mode') == 'fake' for event in events)
        assert events[-1]['event'] == 'state_applied'
