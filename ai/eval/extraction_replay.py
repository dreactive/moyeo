"""Independent extraction replay; no automatic provider tools or user room access."""
import json
from pathlib import Path


def case_task(case):
    task = json.loads((Path(__file__).parents[1] / 'fixtures/agent-task.json').read_text(encoding='utf-8'))
    task.update(room_id='extraction-' + case['id'], goal='extract', current_plan=None, observations=[], constraints=[], questions=[], conversation_context=[])
    task['recent_messages'] = [dict(id=case['id'], author_id='u1', text=case['text'])]
    if case['group'] != 'support':
        task['items'] = []
    return task


def check_case(case, result):
    from ai.grounding import normalized
    issues = []
    names = {normalized(item['title']) for item in result['item_proposals']}
    if names != {normalized(name) for name in case['places']}:
        issues.append('places')
    values = {('budget_krw' if p['key'] == 'budget' else p['key']): p['value'] for p in result['constraint_proposals']}
    if values != case['conditions']:
        issues.append('conditions')
    if result['extraction_report']['status'] == 'failed':
        issues.append('schema_failed')
    return issues
