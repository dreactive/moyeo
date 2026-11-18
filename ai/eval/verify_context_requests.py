"""Actual Qwen/LoRA audit of two historical targets using synthetic auxiliary/provider data."""
import argparse
import asyncio
import json
import math
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from ai.eval.context_requests import case_inputs, ContextAuxiliary, assert_case
from ai.eval.verify_judge_execution import digest
from ai.runtime import create_runtime


async def verify(args):
    protected = dict(base=Path(args.base_model) / 'model.safetensors',
                     adapter=Path(args.adapter) / 'adapter_model.safetensors')
    if args.database:
        protected['database'] = Path(args.database)
    before = {name: digest(path) for name, path in protected.items()}
    task, catalog = case_inputs()
    started = perf_counter()
    runtime = create_runtime(dict(model_backend='local_qwen', provider_mode='fixture',
        auxiliary_backend='fixture', base_model_path=args.base_model, adapter_path=args.adapter,
        max_decision_rounds=2))
    load_ms = round((perf_counter() - started) * 1000, 2)
    auxiliary = ContextAuxiliary()
    runtime.auxiliary = auxiliary
    events = []
    async def sink(event):
        events.append(event)
    started = perf_counter()
    try:
        with patch('ai.providers.fixture.catalog', return_value=catalog):
            result = await runtime.run(task, sink)
        assert_case(result, events, auxiliary)
        for event in events:
            payload = event['payload']
            if event['event'] == 'decision' and payload.get('scores'):
                assert all(math.isfinite(score) for score in payload['scores'])
                assert payload['selected_index'] == max(range(len(payload['scores'])), key=payload['scores'].__getitem__)
    finally:
        await runtime.aclose()
    after = {name: digest(path) for name, path in protected.items()}
    report = dict(passed=True, case='auxiliary-qwen-two-places-history-resolution',
        auxiliary='synthetic_context_outputs', external_auxiliary_model='gpt-6-luna (NOT called; API key empty)',
        model='actual supplied Qwen2.5-1.5B-Instruct + supplied LoRA', provider='fixture (NO external HTTP)',
        load_ms=load_ms, execution_ms=round((perf_counter() - started) * 1000, 2),
        hashes_before=before, hashes_after=after, protected_files_unchanged=before == after,
        auxiliary_calls=auxiliary.calls, result=result, events=events)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    assert before == after, 'Protected files changed; investigate external writers'
    print(json.dumps(dict(output=args.output, passed=True, auxiliary_calls=len(auxiliary.calls),
                          qwen_rounds=2, executed_calls=len(result['observations']), protected_files_unchanged=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-model', required=True)
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--database')
    parser.add_argument('--output', required=True)
    asyncio.run(verify(parser.parse_args()))


if __name__ == '__main__':
    main()
