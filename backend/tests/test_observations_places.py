def test_observations_populate_details_without_trace(room):
    import json
    from pathlib import Path
    from backend.db import Database
    from backend.services.observations import project_observations, get_observations, observed_place
    result = json.loads(Path('docs/contracts/examples/agent-result.example.json').read_text(encoding='utf-8'))
    db = Database(':memory:')
    project_observations(db, 'a', result['observations'])
    assert observed_place(db, 'a', 'fixture:place-a')['menus'][0]['price_krw'] == 10000
    assert observed_place(db, 'b', 'fixture:place-a') is None
    assert get_observations(db, 'a') == result['observations']


def test_used_evidence_ignores_poll_time_and_unselected_place(room):
    import json
    from pathlib import Path
    from copy import deepcopy
    from backend.services.observations import relevant_evidence
    observations = json.loads(Path('docs/contracts/examples/agent-result.example.json').read_text(encoding='utf-8'))['observations']
    first = relevant_evidence(room['current_plan'], observations)
    observations[0]['result']['evidence'][0]['retrieved_at'] = 'later'
    extra = deepcopy(observations[0])
    extra['result']['place']['id'] = 'unused'
    observations.append(extra)
    assert relevant_evidence(room['current_plan'], observations) == first


def test_observation_merge_keeps_latest_value():
    from backend.services.observations import merge_observations
    first = {'tool_name':'get_place_details','arguments':{'place_ref':'p'},'result':{'price':1}}
    second = dict(first, result={'price':2})
    assert merge_observations([first], [second]) == [second]
    assert first['result']['price'] == 1


def test_place_read_preserves_plan_and_votes_and_blocks_other_room(api, agent_result):
    from backend.services.observations import project_observations
    db = api.app.state.db
    project_observations(db, 'room-fixture', agent_result['observations'])
    before = api.get('/api/rooms/room-fixture').json()
    response = api.get('/api/rooms/room-fixture/places/fixture:place-a')
    assert response.status_code == 200
    assert response.json()['place']['id'] == 'fixture:place-a'
    assert api.get('/api/rooms/room-fixture').json() == before
    assert api.get('/api/rooms/room-fixture/places/https:evil').status_code == 404
