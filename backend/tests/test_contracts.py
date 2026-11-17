import asyncio
import json
from pathlib import Path


def test_fixture_port_matches_json_examples():
    from backend.adapters.fixture_agent import FixtureAgentPort
    task = {'run_id': 'r', 'room_id': 'room', 'base_versions': {'plan_revision': 0}}
    result = asyncio.run(FixtureAgentPort().run(task, None))
    assert result['room_id'] == 'room'
    assert result['base_versions'] == task['base_versions']
    assert json.loads(json.dumps(result))['completion'] == 'needs_input'


def test_fixture_context_is_room_scoped():
    import asyncio
    from backend.adapters.fixture_agent import FixtureAgentPort
    async def check():
        port = FixtureAgentPort()
        for room in ('one', 'two'):
            context = {'room_id': room, 'config': {}, 'observations': [
                {'tool_name': 'get_place_details', 'arguments': {'place_ref': 'p'}, 'result': {'room': room}}
            ]}
            assert await port.execute_tool('get_place_details', {'place_ref': 'p'}, context) == {'room': room}
    asyncio.run(check())


def test_trip_config_matches_frozen_input():
    import json
    from pathlib import Path
    from backend.schemas import TripConfig
    source = json.loads(Path('docs/contracts/examples/agent-input.example.json').read_text(encoding='utf-8'))
    assert TripConfig.model_validate(source['config']).model_dump() == source['config']


def test_fixture_does_not_apply_unknown_seed_item_refs():
    import asyncio
    from backend.adapters.fixture_agent import FixtureAgentPort
    task = dict(run_id='new',room_id='new-room',base_versions={},items=[],recent_messages=[])
    result = asyncio.run(FixtureAgentPort().run(task, None))
    assert result['plan_draft'] is None
    assert result['questions'] == []
    assert result['completion'] == 'needs_input'


def test_fixture_preserves_contract_fields_enums_and_timestamps():
    from datetime import datetime
    from backend.adapters.fixture_agent import FixtureAgentPort
    from backend.schemas import Versions
    task = json.loads(Path('docs/contracts/examples/agent-input.example.json').read_text(encoding='utf-8'))
    expected = json.loads(Path('docs/contracts/examples/agent-result.example.json').read_text(encoding='utf-8'))
    result = asyncio.run(FixtureAgentPort().run(task, None))
    assert set(result) == set(expected)
    assert Versions.model_validate(result['base_versions']).model_dump() == task['base_versions']
    evidence = result['observations'][0]['result']['evidence'][0]
    assert evidence['mode'] == 'fixture'
    assert evidence['status'] == 'api_observed'
    assert evidence['provider_updated_at'] is None
    assert datetime.fromisoformat(evidence['retrieved_at']).tzinfo is not None
    assert isinstance(result['run_id'], str)
    assert isinstance(result['observations'][0]['result']['menus'][0]['price_krw'], int)
