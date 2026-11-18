import pytest


def scored_tool_calls(events):
    decisions = {event['step']: event['payload'] for event in events
                 if event['event'] == 'decision' and event['payload'].get('selected_index') is not None}
    calls = [event for event in events if event['event'] == 'tool_call']
    results = {event['call_id']: event['payload'] for event in events if event['event'] == 'tool_result'}
    assert calls
    assert len(calls) == sum(decision['candidates'][decision['selected_index']]['action'] == 'tool'
                             for decision in decisions.values())
    for call in calls:
        decision = decisions[call['step']]
        assert decision['model_mode'] == 'fake' and decision['selection_origin'] == 'fixture_judge'
        assert len(decision['scores']) == decision['candidate_count'] == len(decision['candidates'])
        selected = decision['candidates'][decision['selected_index']]
        assert selected['action'] == 'tool'
        assert (call['payload']['tool_name'], call['payload']['arguments']) == (selected['tool_name'], selected['arguments'])
        assert call['payload']['selection_origin'] == 'fixture_judge'
        assert results[call['call_id']]['tool_name'] == selected['tool_name']
    assert events[-1]['event'] == 'state_applied' and events[-1]['payload']['applied'] is True
    return calls, results


@pytest.mark.integration
def test_fixture_judge_executes_scored_calls_and_persists_observations(room):
    from backend.tests.integration_support import existing_clients
    with existing_clients(room) as (clients, path):
        client = clients[0]
        receipt = client.post(path + '/agent-runs', json={'reason':'manual_replan'})
        client.portal.call(client.app.state.jobs.queue.join)
        db = client.app.state.db
        run_id = receipt.json()['run_id']
        assert db.get('run:' + run_id)['applied']
        assert db.get('room:' + room['room_id'])['current_plan'] == room['current_plan']
        events = db.traces[run_id]['events']
        calls, results = scored_tool_calls(events)
        observations = db.observations[room['room_id']]
        assert len(observations) == len(calls)
        assert {'search_places', 'get_place_details', 'get_car_route'} <= {o['tool_name'] for o in observations}
        for call in calls:
            stored = next(o for o in observations if (o['tool_name'], o['arguments']) ==
                          (call['payload']['tool_name'], call['payload']['arguments']))
            assert stored['result'] == results[call['call_id']]['normalized_result']


@pytest.mark.integration
def test_empty_four_person_room_executes_grounded_search_and_preserves_support_ownership(room):
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
        db = clients[0].app.state.db
        observations = db.observations[snapshot['room_id']]
        traces = [trace for trace in db.traces.values() if trace['room_id'] == snapshot['room_id']]
        assert len(traces) == 1
        assert db.get('run:' + traces[0]['run_id'])['applied'] is True
        assert db.get('processed-message:' + snapshot['room_id']) == response.json()['id']
        calls, results = scored_tool_calls(traces[0]['events'])
        search = next(o for o in observations if o['tool_name'] == 'search_places')
        assert search['arguments'] == {'query': snapshot['items'][0]['title'], 'region': room['config']['region'], 'category': None}
        assert search['result']['places'][0]['id'] == 'fixture:place-a'
        detail = next(o for o in observations if o['tool_name'] == 'get_place_details')
        assert detail['arguments'] == {'place_ref': 'fixture:place-a'}
        for call in calls:
            # Backend assigns persistent item IDs to new proposal references.
            # Search, details and routes carry the exact scored arguments through storage.
            if call['payload']['tool_name'] != 'build_itinerary':
                stored = next(o for o in observations if (o['tool_name'], o['arguments']) ==
                              (call['payload']['tool_name'], call['payload']['arguments']))
                assert stored['result'] == results[call['call_id']]['normalized_result']
        for observation in observations:
            if observation['tool_name'] == 'build_itinerary':
                assert {visit['item_id'] for visit in observation['arguments']['visits']} == {snapshot['items'][0]['id']}
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
def test_late_visit_recalculates_confirmed_deadline_without_changing_confirmation_history(room):
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
        updated = clients[0].get(path).json()
        assert updated['current_plan']['constraint_version'] == updated['versions']['constraint_version']
        assert updated['current_plan']['validation'] == 'conflict'
        time_conflicts = [conflict for conflict in updated['conflicts']
                          if conflict['type'] == 'time' and conflict['blocking'] and late['item_id'] in conflict['affected_item_ids']]
        assert time_conflicts
        assert {conflict['id'] for conflict in time_conflicts} <= set(updated['current_plan']['blocking_conflict_ids'])
        assert updated['confirmed_plan'] == historical
