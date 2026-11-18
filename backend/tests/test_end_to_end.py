import pytest


@pytest.mark.integration
def test_fake_runtime_applies_candidates_without_running_tools(room):
    from backend.tests.integration_support import existing_clients
    with existing_clients(room) as (clients, path):
        client = clients[0]
        receipt = client.post(path + '/agent-runs', json={'reason':'manual_replan'})
        client.portal.call(client.app.state.jobs.queue.join)
        db = client.app.state.db
        run_id = receipt.json()['run_id']
        assert db.get('run:' + run_id)['applied']
        assert db.observations[room['room_id']] == []
        assert db.get('room:' + room['room_id'])['current_plan'] == room['current_plan']
        events = db.traces[run_id]['events']
        assert any(e['event'] == 'decision' and e['payload'].get('candidates') for e in events)
        assert not any(e['event'] in ('tool_call','tool_result') for e in events)
        assert events[-1]['event'] == 'state_applied'


@pytest.mark.integration
def test_empty_four_person_room_extracts_supported_item_without_plan(room):
    from backend.tests.integration_support import four_clients
    with four_clients(room['config']) as (clients, path):
        response = clients[0].post(path+'/messages', json={'text':'가상 A식당 가자'})
        assert response.status_code == 201
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        assert len(snapshot['members']) == 4
        assert len(snapshot['items']) == 1
        assert snapshot['items'][0]['state'] == 'mentioned'
        assert snapshot['current_plan'] is None
        assert clients[0].app.state.db.observations[snapshot['room_id']] == []
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


@pytest.mark.integration
def test_existing_late_visit_plan_is_preserved_while_conditions_are_extracted(room):
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
    room['current_plan']['selected_item_ids'] = [late['item_id']]
    room['current_plan']['item_snapshots'] = [item for item in room['current_plan']['item_snapshots'] if item['id'] == late['item_id']]
    import json
    from pathlib import Path
    detail = json.loads(Path('backend/tests/fixtures/late-place-details.json').read_text(encoding='utf-8'))
    observation = dict(tool_name='get_place_details',arguments={'place_ref':'fixture:place-a'},result=detail,observed_at='2026-11-18T10:00:00+09:00',source_refs=[])
    with existing_clients(room, [observation]) as (clients, path):
        receipt = clients[0].post(path+'/agent-runs', json={'reason':'manual_replan'})
        clients[0].portal.call(clients[0].app.state.jobs.queue.join)
        snapshot = clients[0].get(path).json()
        assert receipt.status_code == 202
        assert snapshot['current_plan'] == room['current_plan']
        historical = snapshot['confirmed_plan']
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
        assert clients[0].get(path).json()['current_plan'] == room['current_plan']
