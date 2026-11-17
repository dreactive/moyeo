import json
from pathlib import Path


class FixtureAgentPort:
    async def run(self, task, emit_trace):
        result = json.loads(Path(__file__).with_name('fixture_result.json').read_text(encoding='utf-8'))
        result.update({key: task[key] for key in ('run_id', 'room_id', 'base_versions')})
        return result

    async def aclose(self):
        pass
