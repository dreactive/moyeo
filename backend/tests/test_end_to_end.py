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
        target = snapshot['current_plan']['confirmation_target']
        for index, client in enumerate(clients):
            confirmed = client.post(path+'/plan/confirm', json={'target':target})
            assert confirmed.status_code == 200
            assert (confirmed.json()['confirmed_plan'] is not None) == (index == 3)
        snapshot = confirmed.json()
        assert snapshot['review_plan']['confirmation_target'] == target
        assert snapshot['confirmed_plan']['confirmation_target'] == target
        assert snapshot['items'][0]['state'] == 'confirmed'


@pytest.mark.integration
def test_existing_late_visit_plan_can_be_recalculated(room):
    from backend.tests.integration_support import existing_clients
    room['config']['day_start_time'] = '10:00'
    room['config']['day_end_time'] = '19:00'
    room['questions'] = []
    for condition in room['constraints']:
        condition['status'] = 'confirmed'
    car = dict(room['config']['fixed_costs'][0],id='car-input',category='car',description='유류·주차·통행료 포함 차량비',unit_price_krw=10000,paid=False)
    room['config']['fixed_costs'].append(car)
    late = room['current_plan']['days'][0]['visits'].pop(0)
    room['current_plan']['days'][0]['visits'] = []
    late.update(date='2026-11-22',start_at='2026-11-22T17:00:00+09:00',end_at='2026-11-22T18:00:00+09:00')
    room['current_plan']['days'][1]['visits'] = [late]
    import json
    from pathlib import Path
    detail = json.loads(Path('backend/tests/fixtures/late-place-details.json').read_text(encoding='utf-8'))
    observation = dict(tool_name='get_place_details',arguments={'place_ref':'fixture:place-a'},result=detail,observed_at='2026-11-18T10:00:00+09:00',source_refs=[])
    with existing_clients(room, [observation]) as (clients, path):
        receipt = clients[0].post(path+'/agent-runs', json={'reason':'manual_replan'})
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        assert receipt.status_code == 202
        assert snapshot['current_plan']['validation'] == 'ready', {'questions':snapshot['questions'],'conflicts':snapshot['conflicts'],'status':snapshot['agent_status']}
        assert len(snapshot['current_plan']['days'][1]['visits']) == 1
        target = snapshot['current_plan']['confirmation_target']
        for client in clients:
            assert client.post(path+'/plan/confirm', json={'target':target}).status_code == 200
        historical = clients[0].get(path).json()['confirmed_plan']
        clients[3].post(path+'/messages', json={'text':'나는 16시까지 귀가해야 해'})
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        condition = next(c for c in snapshot['constraints'] if c['key'] == 'return_by')
        assert condition['owner_id'] == 'u4'
        assert condition['status'] == 'needs_owner_confirmation'
        assert clients[0].post(path+'/constraints/'+condition['id']+'/confirm').status_code == 403
        assert snapshot['confirmed_plan'] == historical
        assert clients[3].post(path+'/constraints/'+condition['id']+'/confirm').status_code == 200
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        conflicted = clients[0].get(path).json()
        conflict = next(c for c in conflicted['conflicts'] if c['type'] == 'time' and c['blocking'])
        assert conflicted['current_plan']['validation'] == 'conflict'
        assert conflicted['confirmed_plan'] == historical
        selected = clients[0].post(path+'/conflicts/'+conflict['id']+'/select', json={'option_id':conflict['options'][0]['id']})
        assert selected.status_code == 202
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        revised = clients[0].get(path).json()
        assert revised['current_plan']['validation'] == 'ready'
        assert revised['current_plan']['cost']['total_krw'] == 90000
        assert revised['confirmations'] == []
        assert revised['confirmed_plan'] == historical
