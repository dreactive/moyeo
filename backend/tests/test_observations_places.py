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
