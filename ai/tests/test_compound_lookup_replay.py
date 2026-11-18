import json
from pathlib import Path

import pytest

from ai.auxiliary import prepare_auxiliary
from ai.judged_runner import run_judged_agent
from ai.tests.test_auxiliary import ScriptedAuxiliary, batch
from ai.tests.test_judged_runner import Judge, Tools
from ai.tests.test_place_route_tools import task


CASES = json.loads(Path('ai/fixtures/auxiliary-compound-lookup-replay.json').read_text(encoding='utf-8-sig'))


def current_case(row):
    value = task()
    source = row['raw']['analysis']['source_message_ids'][0]
    value.update(recent_messages=[dict(id=source,author_id='u1',text=row['source'])],conversation_context=[],questions=[])
    return value


async def test_live_budget_and_details_raw_batch_recovers_both_fields_and_owner_budget():
    row = CASES[0]
    value = current_case(row)
    out = await prepare_auxiliary(value,ScriptedAuxiliary(row['raw']))
    assert [(c['owner_id'],c['value'],c['key']) for c in out['constraint_proposals']]==[('u1',150000,'budget_krw')]
    requests = out['analysis']['requests']
    assert {f for r in requests for f in r['requested_fields']}=={'price','opening_hours'}
    assert all(r['evidence']['quote'] in row['source'] for r in requests)
    assert {'budget_completed_from_source','lookup_aligned_to_source'} <= set(out['extraction_report']['repairs'])


async def test_live_compound_location_raw_batch_cannot_run_old_plan_or_expand_detail_fields():
    row = CASES[1]
    value = current_case(row)
    tools = Tools()
    result = await run_judged_agent(value,Judge(),tools,None,ScriptedAuxiliary(row['raw']))
    assert [(name,args['query']) for name,args in tools.calls]==[
        ('search_places','오동도'),('search_places','여수세계박람회장')]
    assert all(r['requested_fields']==['location'] and r['evidence']['quote'] in row['source']
               for r in result['request_states'])
    assert result['extraction_report']['repairs']==['lookup_aligned_to_source']
    assert result['item_proposals']==result['support_observations']==[]


async def test_omitted_current_compound_lookup_prevents_unrelated_planning_calls():
    value = current_case(CASES[1])
    tools = Tools()
    out = await run_judged_agent(value,Judge(),tools,None,ScriptedAuxiliary(batch()))
    assert not tools.calls
    assert [(q['field'],q['owner_id']) for q in out['questions']]==[('target_places','u1')]


async def test_explicit_cost_and_itinerary_purposes_survive_an_empty_request_list():
    value = current_case(CASES[1])
    value['recent_messages'][0]['text'] = '확인된 비용부터 계산하고 가능한 일정도 보여줘'
    out = await prepare_auxiliary(value,ScriptedAuxiliary(batch()))
    assert {r['intent'] for r in out['analysis']['requests']}=={'cost_estimate','itinerary_plan'}
    assert 'calculation_completed_from_source' in out['extraction_report']['repairs']


def test_empty_raw_hours_are_rendered_as_missing():
    from ai.request_lifecycle import detail_response
    response,gaps = detail_response(dict(place=dict(name='자산공원'),opening_hours=dict(raw_text='[]',intervals=[]),
                                         missing_fields=['opening_hours']))
    assert '[]' not in response
    assert '영업시간' in response and '미확인' in response and 'opening_hours' in gaps


async def test_rejected_lookup_scope_cannot_dispatch_old_plan_calculations():
    value = current_case(CASES[1])
    message = value['recent_messages'][0]
    message['text'] = '친구가 오동도를 찾아 달라고 했어.'
    raw = batch()
    raw['analysis']['requests'] = [dict(intent='place_lookup', target_names=['오동도'], requested_fields=['location'],
                                       evidence=dict(message_id=message['id'],quote=message['text']))]
    tools = Tools()
    result = await run_judged_agent(value,Judge(),tools,None,ScriptedAuxiliary(raw))
    assert not tools.calls and not result.get('request_states')


async def test_alignment_does_not_shorten_a_different_place_name():
    value = current_case(CASES[1])
    value['recent_messages'][0]['text'] = '오동도호텔하고 여수세계박람회장 찾아줘.'
    out = await prepare_auxiliary(value,ScriptedAuxiliary(CASES[1]['raw']))
    assert all('오동도' not in r['target_names'] for r in out['analysis']['requests'])


@pytest.mark.parametrize('reverse_aux_order', [False,True])
async def test_cancellation_in_current_batch_targets_only_earlier_lookup(reverse_aux_order):
    value = current_case(CASES[1])
    texts = ['오동도 찾아줘','오동도 조회 취소해줘','오동도 찾아줘']
    messages = [dict(id=f'm{i}',author_id='u1',text=text) for i,text in enumerate(texts)]
    value['recent_messages'] = messages
    raw = batch()
    rows = [dict(intent='place_lookup',operation='cancel' if i==1 else 'request',target_names=['오동도'],
                 evidence=dict(message_id=m['id'],quote=m['text'])) for i,m in enumerate(messages)]
    raw['analysis']['requests'] = list(reversed(rows)) if reverse_aux_order else rows
    model,tools = Judge(),Tools()
    result = await run_judged_agent(value,model,tools,None,ScriptedAuxiliary(raw))
    states = {r['source_message_id']:r for r in result['request_states']}
    assert states['m0']['status']=='cancelled'
    assert states['m1']['cancelled_request_ids']==[states['m0']['request_id']]
    assert states['m2']['status']=='completed'
    selected_searches = [r for _,choices in model.calls for r in choices if r.get('tool_name')=='search_places']
    assert selected_searches and all(c['request_ids']==[states['m2']['request_id']] for c in selected_searches)


@pytest.mark.parametrize('exact', [True, False])
async def test_field_from_other_target_cannot_authorize_detail_call(exact):
    value = current_case(CASES[1])
    msg = value['recent_messages'][0]
    msg['text']='오동도 위치와 자산공원 영업시간 알려줘'
    raw = batch()
    raw['analysis']['requests'] = [dict(intent='place_lookup',target_names=['오동도'],requested_fields=['opening_hours'],
        evidence=dict(message_id=msg['id'],quote=msg['text'] if exact else '오동도 영업시간'))]
    result = await prepare_auxiliary(value,ScriptedAuxiliary(raw))
    scopes = result['analysis']['requests']
    assert not any('오동도' in r['target_names'] and 'opening_hours' in r['requested_fields'] for r in scopes)
    assert scopes and result['extraction_report']['status']!='failed'
    assert {(n,f) for r in scopes for n in r['target_names'] for f in r['requested_fields']}=={
        ('오동도','location'),('자산공원','opening_hours')}


async def test_verbatim_evidence_does_not_authorize_a_shortened_place_name():
    value = current_case(CASES[1])
    msg = value['recent_messages'][0]
    msg['text']='오동도호텔 찾아줘'
    raw = batch()
    raw['analysis']['requests'] = [dict(intent='place_lookup',target_names=['오동도'],requested_fields=['location'],
        evidence=dict(message_id=msg['id'],quote=msg['text']))]
    result = await prepare_auxiliary(value,ScriptedAuxiliary(raw))
    assert all('오동도' not in r['target_names'] for r in result['analysis']['requests'])


def test_scoped_candidate_independently_rechecks_target_field_attachment():
    from ai.decision_candidates import build_decision_candidates
    from ai.tests.test_review_request_lifecycle import observed
    value = current_case(CASES[1])
    msg = value['recent_messages'][0]
    msg['text']='오동도 위치와 자산공원 영업시간 알려줘'
    value['observations']=[observed('오동도','odong')]
    request = dict(request_id='request:'+msg['id']+':place_lookup',intent='place_lookup',
        operation='request',owner_id=msg['author_id'],source_message_id=msg['id'],status='resolved',
        target_names=['오동도'],target_refs=['odong'],requested_fields=['opening_hours'],
        evidence=dict(message_id=msg['id'],quote=msg['text']))
    assert not build_decision_candidates(value,dict(requests=[request]))['candidates']


async def test_completed_cost_cannot_borrow_an_itinerary_directive():
    value = current_case(CASES[1])
    value['recent_messages'][0]['text']='여행 비용 계산은 끝났으니 가능한 일정도 보여줘'
    result = await prepare_auxiliary(value,ScriptedAuxiliary(batch()))
    assert [r['intent'] for r in result['analysis']['requests']]==['itinerary_plan']


async def test_partially_extracted_coordinated_lookup_keeps_both_requested_names():
    from copy import deepcopy
    value = current_case(CASES[1])
    raw = deepcopy(CASES[1]['raw'])
    raw['analysis']['requests'] = raw['analysis']['requests'][:1]
    tools = Tools()
    result = await run_judged_agent(value,Judge(),tools,None,ScriptedAuxiliary(raw))
    assert [args['query'] for name,args in tools.calls]==['오동도','여수세계박람회장']
    assert all(r['requested_fields']==['location'] for r in result['request_states'])


@pytest.mark.parametrize(('control','cancelled','target_names'), [
    ('자산공원 검색 취소해줘',False,['자산공원']),
    ('오동도호텔 검색 취소해줘',False,['오동도호텔']),
    ('오동도하고 자산공원 조회 취소해줘',False,['오동도','자산공원']),
    ('오동도 조회 취소해줘',True,['오동도']),
    ('오동도 검색은 취소해줘',True,['오동도']),
    ('조회 취소해줘',True,[]),
])
async def test_omitted_cancel_retains_named_or_genuinely_generic_scope(control,cancelled,target_names):
    value = current_case(CASES[1])
    msg = value['recent_messages'][0]
    msg['text']='오동도 찾아줘'
    value['recent_messages'].append(dict(id='cancel',author_id=msg['author_id'],text=control))
    raw = batch()
    raw['analysis']['requests'] = [dict(intent='place_lookup',target_names=['오동도'],requested_fields=['location'],
        evidence=dict(message_id=msg['id'],quote=msg['text']))]
    tools = Tools()
    result = await run_judged_agent(value,Judge(),tools,None,ScriptedAuxiliary(raw))
    states = {r['source_message_id']:r for r in result['request_states']}
    assert states['cancel']['target_names']==target_names
    assert states['cancel']['cancelled_request_ids']==([states[msg['id']]['request_id']] if cancelled else [])
    assert states[msg['id']]['status']==('cancelled' if cancelled else 'completed')
    assert [a['query'] for _,a in tools.calls]==([] if cancelled else ['오동도'])


async def test_coordinated_lookup_recovers_the_full_spaced_name_from_the_source():
    value = current_case(CASES[1])
    msg = value['recent_messages'][0]
    msg['text']='오동도하고 여수 세계박람회장 찾아줘.'
    raw = batch()
    raw['analysis']['requests'] = [dict(intent='place_lookup',target_names=['오동도'],requested_fields=['location'],
        evidence=dict(message_id=msg['id'],quote=msg['text']))]
    tools = Tools()
    result = await run_judged_agent(value,Judge(),tools,None,ScriptedAuxiliary(raw))
    assert [a['query'] for _,a in tools.calls]==['오동도','여수 세계박람회장']
    assert [r['target_names'] for r in result['request_states']]==[['오동도'],['여수 세계박람회장']]
    assert all(r['evidence']['quote'] in msg['text'] and r['requested_fields']==['location'] for r in result['request_states'])


async def test_partial_mixed_lookup_keeps_missing_target_with_its_own_field():
    value = current_case(CASES[1])
    msg = value['recent_messages'][0]
    msg['text']='오동도 위치와 자산공원 영업시간 알려줘'
    raw = batch()
    raw['analysis']['requests'] = [dict(intent='place_lookup',target_names=['오동도'],requested_fields=['location'],
        evidence=dict(message_id=msg['id'],quote='오동도 위치'))]
    out = await prepare_auxiliary(value,ScriptedAuxiliary(raw))
    assert {(n,f) for r in out['analysis']['requests'] for n in r['target_names'] for f in r['requested_fields']}=={
        ('오동도','location'),('자산공원','opening_hours')}


async def test_recorded_visit_proposal_also_retains_the_explicit_speakers_opinion():
    row = CASES[2]
    value = current_case(row)
    out = await prepare_auxiliary(value,ScriptedAuxiliary(row['raw']))
    ref = out['item_proposals'][0]['client_ref']
    assert [(o['item_id'],o['item_version'],o['author_id'],o['stance'],o['source_quote'])
            for o in out['support_observations']]==[(ref,1,'u1','support','자산공원 가자')]
    assert 'opinion_completed_from_source' in out['extraction_report']['repairs']


@pytest.mark.parametrize(('text','expected'), [
    ('자산공원 안좋아.', 'oppose'), ('자산공원은 안 좋아.', 'oppose'),
    ('자산공원 가자?', None), ('자산공원', None), ('친구가 자산공원 가자고 했대.',None),
    ('“자산공원 가자.”라고 들었어.', None), ('만약 자산공원 가자고 하면?', None),
    ('자산공원은 좋아하지 않아. 다른 곳은 좋아.', 'oppose'),
])
async def test_omitted_direct_opinion_requires_a_personal_assertion_about_current_item_version(text,expected):
    value = current_case(CASES[2])
    value['items']=[dict(id='existing-park',title='자산공원',kind='place',item_version=4)]
    value['recent_messages'][0]['text']=text
    out = await prepare_auxiliary(value,ScriptedAuxiliary(batch()))
    assert [(o['item_id'],o['item_version'],o['stance']) for o in out['support_observations']]==(
        [('existing-park',4,expected)] if expected else [])


@pytest.mark.parametrize('text', [
    '친구가 “오동도하고 여수세계박람회장 찾아줘. 내 예산은 15만원이야.”라고 했어.',
    '만약 오동도하고 여수세계박람회장 찾아준다면. 만약 내 예산은 15만원이라면.',
    '오동도하고 여수세계박람회장 찾아주지 마. 내 예산은 15만원이 아니야.',
    '친구가 오동도하고 여수세계박람회장 찾아 달라고 했어. 친구 예산은 15만원이야.',
])
async def test_structured_target_hints_cannot_repair_noncurrent_requests_or_budgets(text):
    value = current_case(CASES[1])
    value['recent_messages'][0]['text'] = text
    out = await prepare_auxiliary(value,ScriptedAuxiliary(CASES[1]['raw']))
    assert not [r for r in out['analysis']['requests'] if r['operation']=='request']
    assert not out['constraint_proposals']
