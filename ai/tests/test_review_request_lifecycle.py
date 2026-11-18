"""Regression cases for sourced requests across judged rounds and saved-state resumes."""
import pytest

from ai.judged_runner import run_judged_agent
from ai.request_lifecycle import superseded_requests
from ai.tests.test_auxiliary import ScriptedAuxiliary, analysis, batch
from ai.tests.test_judged_runner import Judge, Tools, task
from ai.tests.test_request_preparation import place
from ai.tests.test_decision_candidates_requests import canonical_task_and_analysis, add_details


def scenario(text):
    value = task()
    value['recent_messages'][0]['text'] = text
    value['conversation_context'] = []
    return value


def raw(value, *names, intent='place_lookup', quote=None, **fields):
    message = value['recent_messages'][0]
    return dict(intent=intent, target_names=list(names),
                evidence=dict(message_id=message['id'], quote=quote or message['text']), **fields)


async def judged(value, *requests, tools=None, judge=None):
    aux = ScriptedAuxiliary(batch(analysis=analysis(requests=list(requests))))
    return await run_judged_agent(value, judge or Judge(), tools or Tools(), None, aux)


def saved(mid, name):
    return dict(request_id=f'request:{mid}:place_lookup', source_message_id=mid, owner_id='u1',
                intent='place_lookup', operation='request', status='pending', target_refs=[], target_names=[name],
                requested_fields=['location'], evidence=dict(message_id=mid, quote=f'{name} 찾아줘'))


def observed(name, ref, region='여수'):
    return dict(tool_name='search_places', arguments=dict(query=name,region=region,category=None),
                result=dict(places=[place(ref, name, region+' 주소')]),source_refs=['search:'+ref])


@pytest.mark.parametrize('judge_fails', [False, True])
async def test_cancel_revalidates_original_scope_before_retiring(judge_fails):
    value = scenario('돌산공원 조회는 취소해줘')
    original = saved('old', '돌산공원')
    value['pending_requests'] = [original]
    model = Judge([] if judge_fails else None)
    tools = Tools()
    result = await judged(value, raw(value,'돌산공원',operation='cancel'), tools=tools, judge=model)
    assert [c.get('cancelled_request_ids') for c in model.calls[0][1]] == [[original['request_id']]]
    states = {r['request_id']:r for r in result['request_states']}
    if judge_fails:
        assert states.get(original['request_id'],original)['status'] == 'pending'
        assert not result.get('response')
        value.update(recent_messages=[], pending_requests=list({original['request_id']:original, **states}.values()))
        result = await judged(value, tools=tools)
    assert not tools.calls
    assert '취소했습니다' in result['response']
    assert next(r for r in result['request_states'] if r['request_id']==original['request_id'])['status']=='cancelled'


async def test_answered_ambiguous_cancel_retires_only_selected_scope_on_resume():
    value = scenario('조회 취소해줘')
    originals = [saved('a','돌산공원'), saved('b','자산공원')]
    value['pending_requests'] = originals
    first = await judged(value, raw(value,operation='cancel'))
    cancel = first['request_states'][0]
    cancel.update(target_names=['자산공원'],answer=dict(target_names=['자산공원']),status='pending')
    value.update(recent_messages=[],pending_requests=originals+[cancel])
    tools = Tools()
    final = await judged(value,tools=tools)
    assert not any(args.get('query')=='자산공원' for _,args in tools.calls)
    assert next(r for r in final['request_states'] if r['request_id']==originals[1]['request_id'])['status']=='cancelled'


async def test_unanswered_cancel_keeps_ambiguous_targets_available_on_resume():
    value = scenario('조회 취소해줘')
    originals = [saved('a','돌산공원'), saved('b','자산공원')]
    value['pending_requests'] = originals
    first = await judged(value, raw(value,operation='cancel'))
    value.update(recent_messages=[],pending_requests=originals + first['request_states'],questions=first['questions'])
    tools = Tools()
    result = await judged(value,tools=tools)
    assert not tools.calls
    assert result['questions']==first['questions']
    assert all(r['status']=='pending' for r in result['request_states'] if r['request_id'] in {s['request_id'] for s in originals})


async def test_independent_target_continues_after_one_search_fails():
    value = scenario('오동도하고 자산공원 찾아줘')
    class Search(Tools):
        async def execute(self,name,arguments):
            if arguments['query']=='오동도':
                self.calls.append((name,arguments))
                raise RuntimeError('temporary failure')
            return await super().execute(name,arguments)
    tools = Search()
    result = await judged(value,raw(value,'오동도','자산공원'),tools=tools)
    assert [args['query'] for _,args in tools.calls] == ['오동도','자산공원']
    state = result['request_states'][0]
    assert state['completed_target_names']==['자산공원']
    assert [f['target_name'] for f in state['failed_targets']]==['오동도']
    assert state['status']=='failed'


def test_unrelated_owned_search_keeps_previous_open_request():
    old = dict(saved('a','돌산공원'),status='needs_input')
    assert superseded_requests([old],[dict(saved('b','자산공원'),status='resolved')]) == []


async def test_exhausted_history_leads_to_owned_question():
    value = scenario('아까 내가 고른 두 곳 상세 정보 보여줘')
    result = await judged(value,raw(value,intent='place_details'))
    assert [(q['field'],q['target_ref'],q['owner_id']) for q in result['questions']] == [
        ('target_places',result['request_states'][0]['request_id'],'u1')]


async def test_transient_context_completion_can_retry_from_saved_source():
    from ai.tests.test_auxiliary_requests import semantic_task, stages
    value = semantic_task()
    value['base_versions'] = {}
    first, second = stages(value)
    interim = await run_judged_agent(value,Judge(),Tools(),None,ScriptedAuxiliary(first))
    assert interim['request_states'][0]['status']=='needs_context'
    value.update(conversation_context=value['conversation_context']+value['recent_messages'],
                 recent_messages=[],pending_requests=interim['request_states'])
    aux = ScriptedAuxiliary(first,second)
    model = Judge([])
    await run_judged_agent(value,model,Tools(),None,aux)
    assert [stage for stage,_ in aux.calls] == [1,2]
    assert {c['arguments']['place_ref'] for c in model.calls[0][1]}=={'p1','p2'}


async def test_cost_purpose_in_compound_message_survives_auxiliary_omission():
    from ai.tests.test_place_route_tools import task as cost_task
    from ai.tools.costs import calculate_costs
    value = scenario('오동도 위치 찾아주고 여행 비용도 계산해줘')
    value['config']['fixed_costs'] = cost_task()['config']['fixed_costs']
    class ActualCosts(Tools):
        async def execute(self,name,args):
            if name=='calculate_costs':
                self.calls.append((name,args))
                return calculate_costs(**args)
            return await super().execute(name,args)
    tools = ActualCosts()
    result = await judged(value,raw(value,'오동도',quote='오동도 위치 찾아주고'),tools=tools)
    assert {name for name,_ in tools.calls}=={'search_places','calculate_costs'}
    assert {r['intent']:r['status'] for r in result['request_states']} == {
        'place_lookup':'completed','cost_estimate':'completed'}
    assert result['partial_results']['calculate_costs']['known_total_krw']>0


async def test_explicit_cost_with_unpriced_lines_preserves_unknown_total():
    from ai.tools.registry import RegisteredTools
    value = scenario('여행 비용 계산해줘')
    result = await judged(value, raw(value,intent='cost_estimate'), tools=RegisteredTools(value))
    assert result.get('partial_results',{}).get('calculate_costs',{}).get('unknown_line_count',0)>0
    assert result['partial_results']['calculate_costs']['total_krw'] is None


async def test_compound_lookup_updates_a_calculation_whose_canonical_inputs_changed():
    from ai.tools.registry import RegisteredTools
    value = scenario('가상 A식당 위치 찾아주고 여행 비용도 계산해줘')
    value['items'] = [dict(id='existing',kind='place',title='가상 A식당',item_version=1,source_message_ids=[])]
    class CostsFirst(Judge):
        def score_candidates(self,context,candidates):
            return [float(c.get('tool_name')=='calculate_costs') for c in candidates]
    result = await judged(value,raw(value,'가상 A식당',quote='가상 A식당 위치 찾아주고'),
                          tools=RegisteredTools(value),judge=CostsFirst())
    assert result['observations'][0]['tool_name']=='calculate_costs'
    assert result['request_states'][-1]['status']=='completed'
    assert 'calculate_costs' in result['partial_results']


@pytest.mark.parametrize('text', ['어제 여행 비용 계산했어', '여행 비용 계산해 달라고 했대', '여행 비용 계산하지 마'])
async def test_recounted_or_negated_cost_is_not_a_calculation_request(text):
    from ai.tools.registry import RegisteredTools
    value = scenario(text)
    result = await judged(value,raw(value,intent='cost_estimate'),tools=RegisteredTools(value))
    assert not any(r['intent']=='cost_estimate' for r in result.get('request_states',[]))


async def test_explicit_itinerary_progresses_through_route_prerequisites():
    from ai.tools.registry import RegisteredTools
    from ai.tests.test_place_route_tools import task as planning_task
    value = planning_task()
    value.update(recent_messages=[dict(id='new',author_id='u1',text='여행 일정 짜줘')],questions=[])
    value['observations'] = [o for o in value['observations'] if o['tool_name'] in ('search_places','get_place_details')]
    result = await judged(value,raw(value,intent='itinerary_plan'),tools=RegisteredTools(value))
    assert any(r['intent']=='itinerary_plan' and r['status']=='completed' for r in result.get('request_states',[]))
    assert result['partial_results']['build_itinerary']['days']


async def test_same_name_detail_cannot_escape_search_region():
    value = scenario('돌산공원 위치 찾아줘')
    previous = observed('돌산공원','seoul','서울')
    value['observations'] = [previous,dict(tool_name='get_place_details',arguments=dict(place_ref='seoul'),
        result=dict(place=previous['result']['places'][0],menus=[],evidence=[]),source_refs=[])]
    tools = Tools()
    result = await judged(value,raw(value,'돌산공원'),tools=tools)
    assert [args['region'] for _,args in tools.calls]==['여수']
    assert '서울' not in result['request_states'][0]['response']


async def test_wrong_location_detail_cannot_replace_current_search_identity():
    value = scenario('돌산공원 위치 찾아줘')
    regional = observed('돌산공원','same')
    older = observed('돌산공원','same','서울')
    value['observations'] = [older,regional,dict(tool_name='get_place_details',arguments=dict(place_ref='same'),
        result=dict(place=older['result']['places'][0],menus=[],evidence=[]),source_refs=['old-seoul-details'])]
    model = Judge()
    result = await judged(value,raw(value,'돌산공원'),judge=model)
    assert result['request_states'][0]['response']=='돌산공원 · 여수 주소'
    assert 'old-seoul-details' not in model.calls[0][1][0]['source_refs']


async def test_saved_legacy_completed_ref_maps_to_name_and_cached_remaining_ref_is_reported():
    value, source = canonical_task_and_analysis()
    for ref in ('p1','p2'):
        add_details(value,ref)
    original = dict(source['requests'][0],completed_refs=['p1'],pending_refs=['p2'],status='pending')
    value.update(pending_requests=[original],recent_messages=[])
    model = Judge()
    result = await judged(value,judge=model)
    assert len(model.calls)==1 and model.calls[0][1][0]['action']=='direct'
    state = result['request_states'][0]
    assert set(state['completed_target_names'])==set(original['target_names'])
    assert state['status']=='completed'


async def test_empty_route_endpoint_search_has_repairable_owned_question():
    value = scenario('오동도에서 자산공원까지 지금 자동차 경로 알려줘')
    value['observations'] = [observed('자산공원','jasan')]
    result = await judged(value,raw(value,'오동도','자산공원',intent='route_lookup'))
    assert [(q['field'],q['target_name'],q['owner_id']) for q in result['questions']]==[
        ('target_places','오동도','u1')]
    state = result['request_states'][0]
    state.update(target_names=['여수역','자산공원'], answer=dict(target_names=['여수역']),status='pending')
    value.update(recent_messages=[],pending_requests=[state],questions=[dict(result['questions'][0],
        status='answered',answer=state['answer'],answered_by='u1')])
    value['observations'] += result['observations'] + [observed('여수역','station')]
    model = Judge([])
    await judged(value,judge=model)
    assert [(c['tool_name'], c['arguments']['from_ref'], c['arguments']['to_ref']) for c in model.calls[0][1]] == [
        ('get_car_route','station','jasan')]
