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


@pytest.mark.integration
def test_empty_four_person_room_creates_initial_plan(room):
    from backend.tests.integration_support import four_clients
    with four_clients(room['config']) as (clients, path):
        response = clients[0].post(path+'/messages', json={'text':'가상 A식당 가자'})
        assert response.status_code == 201
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        assert len(snapshot['members']) == 4
        assert len(snapshot['items']) == 1
        assert snapshot['items'][0]['state'] == 'mentioned'
        assert snapshot['current_plan'] is not None
        assert snapshot['current_plan']['selected_item_ids'] == [snapshot['items'][0]['id']]
        for client, expected in zip(clients[1:3], ('mentioned','supported')):
            client.post(path+'/messages', json={'text':'가상 A식당 좋아'})
            clients[0].portal.call(clients[0].app.state.jobs.queue.join)
            snapshot = clients[0].get(path).json()
            assert snapshot['items'][0]['state'] == expected
        clients[2].post(path+'/messages', json={'text':'가상 A식당 좋아'})
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        assert len(snapshot['items'][0]['supporter_ids']) == 3
        assert snapshot['confirmations'] == []
        config = dict(room['config'])
        car = dict(config['fixed_costs'][0], id='car-input', category='car', description='유류·주차·통행료 포함 차량비', unit_price_krw=10000, paid=False)
        clients[0].patch(path+'/trip', json={'day_start_time':'10:00','fixed_costs':config['fixed_costs']+[car]})
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        question = next(q for q in snapshot['questions'] if q['field'] == 'menu_selection' and q['status'] == 'open')
        answered = clients[0].post(path+'/questions/'+question['id']+'/answer', json={'value':{'menu_id':'fixture:menu-a','quantity':1,'scope':'per_person'}})
        assert answered.status_code == 200
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        assert snapshot['current_plan']['validation'] == 'ready'
        assert snapshot['current_plan']['cost']['total_krw'] == 130000
