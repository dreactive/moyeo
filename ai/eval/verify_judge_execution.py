"""Explicit fixture auxiliary + real supplied Qwen/LoRA + registered live tools.

This audit never contacts the external auxiliary and never writes a product DB.
Run from the repository root with local weights, env_file and an output path.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from time import perf_counter

from ai.runtime import create_runtime


def digest(path):
    if not path:
        return None
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


class AuditAuxiliary:
    backend = 'fixture-audit'

    def extract(self, task, stage=1):
        message = task['recent_messages'][0]
        # Intentionally include a fabricated budget: grounding must reject it.
        places = ['오동도', '여수엑스포'] if message['id'] == 'audit-places' else []
        analysis = dict(summary=message['text'], needs_context=False, context_queries=[], missing_fields=[],
                        unsupported=False, unsupported_reason='', direct_text='', noop=False)
        if message['id'] == 'audit-question':
            analysis['missing_fields'] = [dict(field='origin', target_ref='anchor:origin',
                text='출발지를 알려주세요.', owner_id=None, source_message_ids=[message['id']])]
        if message['id'] == 'audit-unsupported':
            analysis.update(unsupported=True, unsupported_reason='숙소 예약 결제 기능은 제공하지 않습니다.')
        if message['id'] == 'audit-direct':
            analysis['direct_text'] = '여수'
        return dict(item_proposals=[dict(title=name, mention_text=name, client_ref=name,
                         evidence=dict(message_id=message['id'], quote=name)) for name in places],
                    constraint_proposals=[dict(key='budget_krw', value=100000,
                         evidence=dict(message_id=message['id'], quote=message['text']))] if places else [],
                    support_observations=[], analysis=analysis)


def audit_task(case):
    message_id, text = case
    return dict(run_id=message_id, room_id='isolated-judge-audit', goal='new_message',
                base_versions=dict(participant_version=1, constraint_version=1, evidence_version=1, plan_revision=0),
                recent_messages=[dict(id=message_id, author_id='audit-user', text=text)],
                conversation_context=[], members=[dict(user_id='audit-user', name='검증')],
                config=dict(region='여수', start_date='2026-11-21', end_date='2026-11-21', transport='car',
                            origin=None, destination=None, lodging=None, day_start_time='09:00', day_end_time='18:00'),
                items=[], constraints=[], questions=[], observations=[], current_plan=None, user_selection=None)


async def verify(args):
    protected = dict(base=Path(args.base_model) / 'model.safetensors',
                     adapter=Path(args.adapter) / 'adapter_model.safetensors')
    for name in ('config.json', 'tokenizer.json', 'tokenizer_config.json'):
        protected['base_' + name] = Path(args.base_model) / name
    protected['adapter_config'] = Path(args.adapter) / 'adapter_config.json'
    if args.database:
        protected['database'] = Path(args.database)
        for suffix in ('-wal', '-shm'):
            candidate = Path(args.database + suffix)
            if candidate.exists():
                protected['database' + suffix] = candidate
    before = {key: digest(path) for key, path in protected.items()}
    runtime = create_runtime(dict(model_backend='local_qwen', provider_mode=args.provider,
        base_model_path=args.base_model, adapter_path=args.adapter, env_file=args.env_file,
        auxiliary_backend='fixture', max_decision_rounds=1))
    runtime.auxiliary = AuditAuxiliary()
    results = []
    try:
        for case in [('audit-places', '오동도랑 여수엑스포 찾아줘.'),
                     ('audit-question', '출발지는 아직 안 정했어.'),
                     ('audit-unsupported', '숙소 예약 결제해줘.'),
                     ('audit-direct', '여수')]:
            events = []
            async def sink(event):
                events.append(event)
            started = perf_counter()
            result = await runtime.run(audit_task(case), sink)
            scored = [event['payload'] for event in events if event['event'] == 'decision' and event['payload'].get('scores')]
            assert len(scored) == 1, f'{case[0]}: judge did not produce scores'
            decision = scored[0]
            assert decision['selected_index'] == max(range(len(decision['scores'])), key=decision['scores'].__getitem__)
            selected = decision['candidates'][decision['selected_index']]
            if case[0] == 'audit-places':
                assert not result['constraint_proposals'], 'Ungrounded budget was accepted'
                assert len(decision['candidates']) == 2, 'Expected two real calls without padding'
                assert len(result['observations']) == 1, 'Qwen-selected registered tool did not complete'
                observation = result['observations'][0]
                assert (selected['tool_name'], selected['arguments']) == (observation['tool_name'], observation['arguments'])
                assert observation['result']['places'], 'Live search returned no places'
            else:
                assert not result['observations']
                expected = {'audit-question': 'ask', 'audit-unsupported': 'unsupported', 'audit-direct': 'direct'}
                assert selected['action'] == expected[case[0]]
            results.append(dict(case=case[0], duration_ms=round((perf_counter() - started)*1000, 2),
                                result=result, events=events))
    finally:
        await runtime.aclose()
    after = {key: digest(path) for key, path in protected.items()}
    report = dict(auxiliary='fixture-audit (external API NOT verified)', model='local_qwen + supplied LoRA',
                  provider=args.provider, hashes_before=before, hashes_after=after,
                  protected_files_unchanged=before == after, cases=results)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    assert before == after, 'Protected files changed during audit; investigate external writers'
    print(json.dumps(dict(output=args.output, cases=len(results), protected_files_unchanged=True)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-model', required=True)
    parser.add_argument('--adapter', required=True)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('--provider', choices=['live', 'fixture'], default='live')
    parser.add_argument('--database')
    parser.add_argument('--output', required=True)
    asyncio.run(verify(parser.parse_args()))


if __name__ == '__main__':
    main()
