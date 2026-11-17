import json
from pathlib import Path


class FixtureAgentPort:
    async def run(self, task, emit_trace):
        result = json.loads(Path(__file__).with_name('fixture_result.json').read_text(encoding='utf-8'))
        result.update({key: task[key] for key in ('run_id', 'room_id', 'base_versions')})
        if 'items' in task and not set(result['plan_draft']['selected_item_ids']) <= {item['id'] for item in task['items']}:
            result.update(plan_draft=None, questions=[], completion='needs_input', last_processed_message_id=None)
        return result

    async def aclose(self):
        pass

    async def execute_tool(self, name, arguments, context):
        for observation in reversed(context['observations']):
            if observation['tool_name'] == name and observation['arguments'] == arguments:
                return observation['result']
        raise ValueError('No matching fixture observation')
