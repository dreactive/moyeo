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
    if "support" in case and {p["stance"] for p in result["support_observations"]} != ({case["support"]} if case["support"] else set()):
        issues.append("support")
    return issues + provenance_issues(case, result)


def provenance_issues(case, result):
    for key in ('item_proposals', 'constraint_proposals'):
        for proposal in result[key]:
            if proposal['source_message_ids'] != [case['id']] or proposal.get('owner_id', 'u1') != 'u1':
                return ['provenance']
    return []


async def replay_case(runtime, case):
    import time
    events = []
    async def sink(event):
        events.append(event)
    started = time.perf_counter()
    result = await runtime.run(case_task(case), sink)
    issues = check_case(case, result)
    return dict(id=case['id'], group=case['group'], critical=case.get('critical',False),
                passed=not issues, issues=issues, seconds=time.perf_counter() - started,
                tool_calls=sum(e['event'] == 'tool_call' for e in events), result=result)


def summarize(rows):
    from statistics import median
    from math import ceil
    seconds = sorted(row['seconds'] for row in rows)
    return dict(total=len(rows), passed=sum(row['passed'] for row in rows),
                critical_passed=all(row['passed'] for row in rows if row['critical']),
                unexpected_conditions=sum('conditions' in row['issues'] for row in rows),
                provenance_errors=sum('provenance' in row['issues'] for row in rows),
                schema_failures=sum(row['result']['extraction_report']['status'] == 'failed' for row in rows),
                tool_calls=sum(row['tool_calls'] for row in rows),
                p50_seconds=median(seconds), p95_seconds=seconds[ceil(len(seconds)*.95)-1])


from contextlib import contextmanager


@contextmanager
def collect_generations(model):
    import time
    original, metrics = model.generate, []
    def measured(**kwargs):
        started = time.perf_counter()
        output = original(**kwargs)
        metrics.append(dict(tokens=len(output[0]) - kwargs['input_ids'].shape[-1], seconds=time.perf_counter() - started))
        return output
    model.generate = measured
    try:
        yield metrics
    finally:
        model.generate = original


async def replay_modes(runtime, cases, modes, metrics=None):
    from contextlib import nullcontext
    from unittest.mock import patch
    reports = {}
    for mode in modes:
        rows = []
        with patch('ai.models.qwen_generation.extraction_options', return_value={}) if mode == 'unconstrained' else nullcontext():
            for case in cases:
                offset = len(metrics or [])
                row = await replay_case(runtime, case)
                row["generations"] = (metrics or [])[offset:]
                rows.append(row)
                print(json.dumps(dict(mode=mode, id=row['id'], passed=row['passed'], issues=row['issues'], seconds=row['seconds']), ensure_ascii=False), flush=True)
        reports[mode] = dict(summary=summarize(rows), rows=rows)
    return reports


async def evaluate(config, cases, modes):
    from contextlib import nullcontext
    from ai.runtime import create_runtime
    runtime = create_runtime(config)
    try:
        await replay_case(runtime, dict(id='warmup', group='negative', text='안녕', places=[], conditions={}))
        model = getattr(runtime.model.backend, 'model', None)
        with collect_generations(model) if model is not None else nullcontext([]) as metrics:
            return await replay_modes(runtime, cases, modes, metrics)
    finally:
        await runtime.aclose()
