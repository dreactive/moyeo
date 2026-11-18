import json
from copy import deepcopy

import pytest

from ai import auxiliary
from ai.runtime import AgentRuntime
from ai.tests.test_auxiliary import ScriptedAuxiliary, analysis, batch, evidence
from ai.tests.test_auxiliary_requests import request, semantic_task, stages
from ai.tests.test_judged_runner import Judge, task


def lookup(value):
    current = value['recent_messages'][0]
    return batch(analysis=analysis(requests=[dict(intent='place_lookup', target_names=['오동도'],
        requested_fields=['location'], evidence=evidence(current['text'], current['id']))]))


async def prepared(value, model, previous=None):
    extract = getattr(auxiliary, 'extract_auxiliary', None)
    assert extract is not None, 'The raw extraction API must exist'
    return await extract(value, model, previous=previous)


def ground(value, envelope):
    grounding = getattr(auxiliary, 'ground_auxiliary', None)
    assert grounding is not None, 'The fresh grounding API must exist'
    return grounding(value, envelope)


async def test_explicit_lookup_uses_latest_places_without_another_extraction(monkeypatch):
    value = task()
    value['recent_messages'][0].update(text='오동도 찾아줘', seq=4)
    model = ScriptedAuxiliary(lookup(value))
    real_ground = auxiliary.ground_batch

    def no_ground(*args):
        pytest.fail('The extraction stage attempted grounding')

    with monkeypatch.context() as patch:
        patch.setattr(auxiliary, 'ground_batch', no_ground)
        envelope = json.loads(json.dumps(await prepared(value, model), ensure_ascii=False))
    assert auxiliary.ground_batch is real_ground
    value['config']['region'] = '제주'
    value['observations'] = [dict(tool_name='search_places', arguments=dict(region='제주'),
        result=dict(places=[dict(id='latest', name='오동도')]))]
    result = ground(value, envelope)
    assert result['analysis']['requests'][0]['target_refs'] == ['latest']
    assert len(model.calls) == 1


@pytest.mark.parametrize('field,change', [
    ('room_id', 'elsewhere'), ('run_id', 'another-run'),
    ('recent_messages', []), ('members', []),
])
async def test_mismatched_prepared_room_run_range_or_membership_is_rejected(field, change):
    value = task()
    envelope = await prepared(value, ScriptedAuxiliary(batch()))
    value[field] = change
    with pytest.raises(ValueError) as raised:
        ground(value, envelope)
    assert raised.value.code == 'prepared_source_invalid'


@pytest.mark.parametrize('field,change', [
    ('author_id', 'u2'), ('text', '다른 글'), ('seq', 2),
])
async def test_changed_source_provenance_is_rejected(field, change):
    value = task()
    value['recent_messages'][0]['seq'] = 1
    envelope = await prepared(value, ScriptedAuxiliary(batch()))
    value['recent_messages'][0][field] = change
    with pytest.raises(ValueError) as raised:
        ground(value, envelope)
    assert raised.value.code == 'prepared_source_invalid'


async def test_changed_context_requires_one_extraction_stage_refresh():
    value = semantic_task()
    first, second = stages(value)
    latest = deepcopy(value)
    latest['conversation_context'][0].update(text='한밭수목원하고 대전시립미술관으로 하자.')
    refreshed = batch(analysis=analysis(requests=[request(
        latest, ['한밭수목원', '대전시립미술관'], context=[
            evidence('한밭수목원하고 대전시립미술관으로 하자.', latest['conversation_context'][0]['id'])])]))
    model = ScriptedAuxiliary(first, second, refreshed)
    envelope = await prepared(value, model)
    with pytest.raises(ValueError) as raised:
        ground(latest, envelope)
    assert raised.value.code == 'prepared_context_stale'
    envelope = await prepared(latest, model, previous=envelope)
    result = ground(latest, envelope)
    assert result['analysis']['requests'][0]['target_refs'] == ['p1', 'p3']
    assert [stage for stage, _ in model.calls] == [1, 2, 2]
    latest['conversation_context'][0].update(text='엑스포과학공원으로 하자.')
    result = ground(latest, envelope)
    assert not any(r['target_refs'] for r in result['analysis']['requests'])
    assert len(model.calls) == 3


async def test_failed_refresh_holds_contextual_work_and_keeps_explicit_budget():
    value = semantic_task()
    first, second = stages(value)
    source = value['recent_messages'][0]
    source['text'] += ' 내 예산은 15만원이야.'
    first['constraint_proposals'] = [dict(key='budget_krw', value=150000,
        evidence=evidence('내 예산은 15만원이야.', source['id']))]
    model = ScriptedAuxiliary(first, second)
    envelope = await prepared(value, model)
    value['conversation_context'] = []
    result = ground(value, await prepared(value, model, previous=envelope))
    assert [(c['owner_id'], c['value']) for c in result['constraint_proposals']] == [('u1', 150000)]
    assert not any(r['target_refs'] for r in result['analysis']['requests'])
    assert result['extraction_report']['status'] == 'filtered'
    assert len(model.calls) == 3


async def test_deferred_execution_preserves_facts_and_request_with_no_judge():
    value = task()
    value['recent_messages'][0]['text'] = '오동도 찾아줘. 내 예산은 15만원이야.'
    raw = lookup(value)
    raw['analysis']['requests'][0]['evidence']['quote'] = '오동도 찾아줘'
    runtime = AgentRuntime({})
    judge = Judge()
    runtime.model = judge
    runtime.auxiliary = ScriptedAuxiliary(raw)
    extract = getattr(runtime, 'extract', None)
    assert extract is not None, 'Runtime must be able to extract separately'
    envelope = await extract(value)
    value['_defer_execution'] = True
    result = await runtime.run_prepared(value, envelope, None)
    assert result['decision_report']['reason'] == 'newer_messages_pending'
    assert result['last_processed_message_id'] == 'm-new'
    assert result['plan_draft'] is None and not result['observations']
    assert result['constraint_proposals'][0]['value'] == 150000
    assert [(r['status'], r['target_names']) for r in result['request_states']] == [('pending', ['오동도'])]
    assert not judge.calls and len(runtime.auxiliary.calls) == 1


async def test_queued_item_mention_binds_latest_exact_title():
    value = task()
    raw = batch(item_proposals=[dict(title='오동도', mention_text='오동도',
        client_ref='local', existing_item_id='prior', evidence=evidence('오동도 가자', 'm-new'))])
    value['items'] = [dict(id='prior', title='오동도', item_version=1, state='mentioned')]
    model = ScriptedAuxiliary(raw)
    envelope = await prepared(value, model)
    value['items'] = [dict(id='latest', title='오동도', item_version=2, state='mentioned')]
    result = ground(value, envelope)
    assert not result['item_proposals']
    assert result['extraction_report']['status'] == 'ok'
    assert len(model.calls) == 1


async def test_saved_context_retry_extracts_once_and_never_advances_history_cursor():
    value = semantic_task()
    value['base_versions'] = {}
    first, second = stages(value)
    runtime = AgentRuntime({})
    runtime.model = Judge([])
    runtime.auxiliary = ScriptedAuxiliary(first)
    result = await runtime.run(value, None)
    assert result['request_states'][0]['status'] == 'needs_context'
    value.update(conversation_context=value['conversation_context'] + value['recent_messages'],
        recent_messages=[], pending_requests=result['request_states'])
    runtime.auxiliary = ScriptedAuxiliary(first, second)
    extract = getattr(runtime, 'extract', None)
    assert extract is not None, 'Runtime must prepare saved context retries'
    envelope = await extract(value)
    assert envelope['source_mode'] == 'saved_context_retry'
    result = await runtime.run_prepared(value, envelope, None)
    assert result['last_processed_message_id'] is None
    assert result['request_states'][0]['target_refs'] == ['p1', 'p2']
    assert [stage for stage, _ in runtime.auxiliary.calls] == [1, 2]



async def test_saved_work_added_after_extraction_resumes_with_fresh_request_state():
    value = task()
    value['recent_messages'] = []
    runtime = AgentRuntime({'max_decision_rounds': 1})
    runtime.model = Judge([])
    runtime.auxiliary = ScriptedAuxiliary(batch())
    envelope = await runtime.extract(value)
    source = dict(id='saved', author_id='u1', text='오동도 찾아줘', seq=1)
    value['conversation_context'] = [source]
    value['pending_requests'] = [dict(intent='place_lookup', request_id='request:saved:place_lookup', owner_id='u1',
        source_message_id='saved', evidence=evidence(source['text'], 'saved'), target_names=['오동도'], target_refs=[],
        requested_fields=['location'], operation='request', status='pending')]
    result = await runtime.run_prepared(value, envelope, None)
    assert result['request_states'][0]['request_id'] == 'request:saved:place_lookup'
    assert runtime.model.calls[0][1][0]['arguments']['query'] == '오동도'
    assert result['last_processed_message_id'] is None
    assert len(runtime.auxiliary.calls) == 1


async def test_failed_refresh_cannot_apply_an_indirect_cancellation():
    value = task()
    source = value['recent_messages'][0]
    source['text'] = '아까 그 요청 취소해줘'
    value['pending_requests'] = [dict(request_id='replaced', intent='place_lookup', owner_id=source['author_id'],
        source_message_id='older', target_names=['오동도'], status='pending')]
    first = batch(analysis=analysis(requests=[dict(intent='place_lookup', operation='cancel',
        evidence=evidence(source['text'], source['id']))]))
    model = ScriptedAuxiliary(first)
    envelope = await prepared(value, model)
    value['pending_requests'][0]['request_id'] = 'newest'
    result = ground(value, await prepared(value, model, previous=envelope))
    request_state = result['analysis']['requests'][0]
    assert request_state['status'] == 'needs_input'
    assert request_state['cancelled_request_ids'] == []
    assert len(model.calls) == 2
