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
