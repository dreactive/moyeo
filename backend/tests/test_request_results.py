from copy import deepcopy

import pytest
from fastapi import HTTPException


def blank_result(result):
    value = deepcopy(result)
    value.update(item_proposals=[], constraint_proposals=[], support_observations=[],
                 observations=[], questions=[], conflicts=[], plan_draft=None)
    return value


def request(room, **changes):
    message = room['messages'][-1]
    value = dict(request_id='request:test', intent='place_lookup', operation='request',
                 owner_id=message['author_id'], source_message_id=message['id'],
                 evidence=dict(message_id=message['id'], quote=message['text']),
                 target_names=[], target_refs=[], excluded_refs=[], status='pending')
    return dict(value, **changes)


def test_new_results_keep_terminal_request_history(room, agent_result):
    from backend.services.agent_apply import prepare_result
    previous = request(room, request_id='request:old', status='completed', response='실제 결과')
    room['agent_requests'] = [previous]
    result = blank_result(agent_result)
    result['request_states'] = [request(room)]
    updated, _ = prepare_result(room, result, [])
    assert next(r for r in updated['agent_requests'] if r['request_id']=='request:old') == previous


def test_empty_question_result_does_not_delete_unanswered_question(room, agent_result):
    from backend.services.agent_apply import prepare_result
    before = deepcopy(room['questions'])
    assert any(q['status']=='open' for q in before)
    updated, _ = prepare_result(room, blank_result(agent_result), [])
    assert updated['questions'] == before


def test_partial_output_requires_matching_selected_tool_observation(room, agent_result):
    from backend.services.agent_apply import prepare_result
    result = blank_result(agent_result)
    result['partial_results'] = {'calculate_costs': deepcopy(room['current_plan']['cost'])}
    with pytest.raises(ValueError, match='partial|Partial'):
        prepare_result(room, result, [])


def test_actual_partial_calculation_is_visible_without_new_plan(room, agent_result):
    from backend.services.agent_apply import prepare_result
    result = blank_result(agent_result)
    cost = deepcopy(room['current_plan']['cost'])
    cost['total_krw'] = None
    cost['unknown_line_count'] = 1
    result['observations'] = [dict(tool_name='calculate_costs', arguments={}, result=cost,
                                   source_refs=[], observed_at='2026-11-19T09:00:00+09:00')]
    result['partial_results'] = {'calculate_costs': deepcopy(cost)}
    updated, _ = prepare_result(room, result, [])
    assert updated['current_plan'] == room['current_plan']
    assert updated['agent_results']['calculate_costs'] == cost
    assert updated['agent_results']['versions'] == updated['versions']
    assert updated['agent_results']['run_id'] == result['run_id']


def test_request_target_question_accepts_only_owner_and_offered_observed_place(room):
    from backend.services.questions import answer_question
    value = request(room, status='needs_input', target_names=['공원'])
    room['agent_requests'] = [value]
    q = dict(id='question:lookup', field='target_places', target_ref=value['request_id'],
             owner_id=value['owner_id'], related_item_ids=[], text='어느 공원인가요?',
             status='open', answer=None, answered_by=None,
             place_choices=[dict(place_ref='known:p', name='관측 공원', address='여수')])
    room['questions'] = [q]
    observation = dict(tool_name='search_places', arguments=dict(query='공원',region='여수',category=None),
                       result=dict(places=[dict(id='known:p', name='관측 공원', address='여수')]))
    before = deepcopy(room['items'])
    other = next(m['user_id'] for m in room['members'] if m['user_id'] != value['owner_id'])
    with pytest.raises(HTTPException) as denied:
        answer_question(room, q['id'], other, {'target_names':['관측 공원'],'place_ref':'known:p'}, [observation])
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException):
        answer_question(room, q['id'], value['owner_id'], {'target_names':['다른 지점'],'place_ref':'invented:p'}, [observation])
    answer_question(room, q['id'], value['owner_id'], {'target_names':['관측 공원'],'place_ref':'known:p'}, [observation])
    assert room['agent_requests'][0]['target_refs'] == ['known:p']
    assert room['agent_requests'][0]['answer']['place_ref'] == 'known:p'
    assert room['items'] == before  # answering lookup is never a support vote


def test_unplaced_items_change_plan_hash_and_are_preserved(room):
    from backend.services.planning import build_plan
    draft = {key:deepcopy(room['current_plan'][key]) for key in
             ('selected_item_ids','days','cost','validation','blocking_conflict_ids')}
    first = build_plan(room, draft, [])
    draft['unplaced_items'] = [dict(item_id=room['items'][0]['id'],place_ref=None,reason='경로 미확인')]
    draft['missing_observations'] = [dict(field='route',reason='경로 미확인')]
    draft['validation'] = 'needs_input'
    second = build_plan(room, draft, [])
    assert second['unplaced_items'] == draft['unplaced_items']
    assert first['content_hash'] != second['content_hash']


@pytest.mark.parametrize('field,target,answer',[
    ('region','config:region',{'value':'여수'}),
    ('route_departure','request:test',{'value':'2099-11-21T09:00:00+09:00'}),
])
def test_missing_search_and_route_inputs_have_actionable_answers(room,field,target,answer):
    from backend.services.questions import answer_question
    value=request(room,status='needs_input',intent='route_lookup')
    room['agent_requests']=[value]
    q=dict(id='q-missing',owner_id=value['owner_id'],field=field,target_ref=target,text='입력',
           related_item_ids=[],status='open',answer=None,answered_by=None)
    room['questions']=[q]
    answer_question(room,q['id'],value['owner_id'],answer)
    if field=='region':
        assert room['config']['region']=='여수'
    else:
        assert room['agent_requests'][0]['departure_at']==answer['value']


def test_route_coordinate_read_does_not_execute_an_unselected_detail_tool(api,monkeypatch):
    from backend.services.observations import project_observations
    place=dict(id='observed:p',name='관측 공원',address='여수',latitude=34.7,longitude=127.7)
    project_observations(api.app.state.db,'room-fixture',[
        dict(tool_name='search_places',arguments=dict(query='관측 공원',region='여수',category=None),
             result=dict(places=[place]),observed_at='2026-11-19T09:00:00+09:00',source_refs=[])])
    async def no_unselected_tool(*args):
        raise AssertionError('coordinate display must not start details collection')
    monkeypatch.setattr(api.app.state.agent,'execute_tool',no_unselected_tool)
    response=api.get('/api/rooms/room-fixture/places/observed:p?location_only=true')
    assert response.status_code==200
    assert response.json()['place']==place
    assert response.json()['opening_hours'] is None


def test_cancellation_closes_existing_lookup_question_without_erasing_history(room,agent_result):
    from backend.services.agent_apply import prepare_result
    from backend.services.questions import answer_question
    previous=request(room,status='needs_input')
    room['agent_requests']=[previous]
    q=dict(id='q-target',owner_id=previous['owner_id'],field='target_places',target_ref=previous['request_id'],
           related_item_ids=[],text='대상 확인',status='open',answer=None,answered_by=None)
    room['questions']=[q]
    result=blank_result(agent_result)
    result['request_states']=[dict(previous,status='cancelled')]
    result['questions']=[deepcopy(q)]
    updated,_=prepare_result(room,result,[])
    assert updated['questions'][0]['status']=='cancelled'
    with pytest.raises(HTTPException) as closed:
        answer_question(updated,q['id'],previous['owner_id'],{'target_names':['오동도']})
    assert closed.value.status_code==409
