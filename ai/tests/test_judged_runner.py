import copy
import json
from pathlib import Path

import pytest


def task():
    value = json.loads(Path('ai/fixtures/agent-task.json').read_text(encoding='utf-8'))
    value.update(goal='new_message', items=[], observations=[], questions=[], current_plan=None)
    value['recent_messages'] = [dict(id='m-new', author_id='u1', text='오동도 가자')]
    for name in ('origin', 'destination', 'lodging'):
        value['config'][name] = None
    value['config']['fixed_costs'] = []  # isolate the new lookup, no independent partial cost task
    return value


def extracted():
    return dict(item_proposals=[dict(client_ref='new:odong', kind='place', title='오동도',
                                    source_message_ids=['m-new'])], constraint_proposals=[],
                support_observations=[], questions=[], extraction_report=dict(status='ok'),
                analysis=dict(summary='오동도 방문 요청', source_message_ids=['m-new']))


class Judge:
    mode = 'local_qwen'
    def __init__(self, scores=None):
        self.calls = []
        self.scores = scores
    def score_candidates(self, context, candidates):
        self.calls.append((copy.deepcopy(context), copy.deepcopy(candidates)))
        return self.scores if self.scores is not None else list(reversed(range(len(candidates))))
    def generate_json(self, request):
        raise AssertionError('Qwen must only score')


class Tools:
    mode = 'live'
    def __init__(self):
        self.calls = []
    def restore(self, value):
        pass
    async def execute(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        return {'places': [], 'provenance': {'source': 'http', 'provider': 'test-provider'}}


async def run(monkeypatch, value=None, output=None, model=None, tools=None, is_current=None):
    from ai.judged_runner import run_judged_agent
    async def prepare(*args):
        return copy.deepcopy(output if output is not None else extracted())
    monkeypatch.setattr('ai.auxiliary.prepare_auxiliary', prepare)
    events = []
    async def sink(event):
        events.append(event)
    model, tools = model or Judge(), tools or Tools()
    result = await run_judged_agent(value or task(), model, tools, sink, object(), is_current, max_rounds=1)
    return result, model, tools, events


async def test_actual_candidate_count_and_scored_arguments_are_executed(monkeypatch):
    result, model, tools, events = await run(monkeypatch)
    assert len(model.calls) == 1
    context, candidates = model.calls[0]
    assert len(candidates) == 1  # no invented fallback candidates
    assert tools.calls == [(candidates[0]['tool_name'], candidates[0]['arguments'])]
    assert tools.calls[0][1] == dict(query='오동도', region='여수', category=None)
    assert result['observations'][0]['result']['places'] == []
    decision = next(e['payload'] for e in events if e['event'] == 'decision' and e['step'] == 1)
    assert decision['scores'] == [0.0] and decision['selected_index'] == 0
    assert decision['single_candidate'] is True
    assert [e['event'] for e in events][-2:] == ['tool_call', 'tool_result']


@pytest.mark.parametrize('scores', [[float('nan')], [], [1, 2]])
async def test_bad_judge_result_holds_without_fallback(monkeypatch, scores):
    result, model, tools, events = await run(monkeypatch, model=Judge(scores))
    assert not tools.calls and result['completion'] == 'needs_input'
    assert result['decision_report']['status'] == 'failed'


async def test_stale_request_never_executes_tool(monkeypatch):
    result, model, tools, events = await run(monkeypatch, is_current=lambda: False)
    assert not tools.calls and result['decision_report']['status'] == 'stale'


async def test_opposition_is_previewed_before_tool_readiness(monkeypatch):
    output = extracted()
    output['support_observations'] = [dict(item_id='new:odong', author_id='u1', stance='oppose',
                                           source_message_id='m-new')]
    result, model, tools, events = await run(monkeypatch, output=output)
    assert not tools.calls and not model.calls
    assert result['item_proposals']  # pending mention is preserved


async def test_failed_auxiliary_does_not_score_or_advance(monkeypatch):
    output = extracted()
    output['extraction_report'] = dict(status='failed', issue_codes=['missing_credentials'])
    output['last_processed_message_id'] = None
    result, model, tools, events = await run(monkeypatch, output=output)
    assert not model.calls and not tools.calls
    assert result['last_processed_message_id'] is None


async def test_selected_question_only_and_no_direct_side_effect(monkeypatch):
    output = extracted()
    output['item_proposals'] = []
    output['analysis'].update(missing_fields=[dict(field='origin', target_ref='anchor:origin',
                text='출발지를 알려주세요.', source_message_ids=['m-new'])], direct_text='오동도')
    value = task()
    value['config']['origin'] = None
    result, model, tools, events = await run(monkeypatch, value=value, output=output)
    assert model.calls and not tools.calls
    assert len(result['questions']) == 1 and result['questions'][0]['field'] == 'origin'
    assert result['decision_report']['action'] == 'ask'


async def test_tool_selection_preserves_preexisting_open_questions(monkeypatch):
    from ai.questions import question
    value = task()
    previous = question('origin', 'anchor:origin', '기존 출발지 질문')
    value['questions'] = [previous]
    result, model, tools, events = await run(monkeypatch, value=value)
    assert tools.calls
    assert result['questions'] == [previous]


async def test_new_question_does_not_replace_other_unresolved_questions(monkeypatch):
    from ai.questions import question
    value = task()
    previous = question('lodging', 'anchor:lodging', '기존 숙소 질문')
    value['questions'] = [previous]
    output = extracted()
    output['item_proposals'] = []
    output['analysis']['missing_fields'] = [dict(field='origin', target_ref='anchor:origin',
        text='출발지를 알려주세요.', source_message_ids=['m-new'])]
    result, model, tools, events = await run(monkeypatch, value=value, output=output)
    assert result['questions'][0] == previous
    assert {q['field'] for q in result['questions']} == {'origin', 'lodging'}


async def test_replan_recalculates_after_hidden_config_basis_changes():
    from ai.runtime import create_runtime
    from ai.tests.test_place_route_tools import task as planning_task
    value = planning_task()
    value.update(goal='manual_replan', recent_messages=[], questions=[])
    runtime = create_runtime(dict(model_backend='fake', provider_mode='fixture'))
    try:
        first = await runtime.run(value, None)
        assert {'build_itinerary', 'calculate_costs'} <= {o['tool_name'] for o in first['observations']}
        value['observations'].extend(first['observations'])
        value['config']['day_end_time'] = '10:00'
        second = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    assert {'build_itinerary', 'calculate_costs'} <= {o['tool_name'] for o in second['observations']}
    assert second['plan_draft'] is not None
    assert second['plan_draft']['validation'] != 'ready'


def test_new_place_joins_existing_plan_after_its_search_is_observed():
    from ai.judged_runner import preview_proposals
    from ai.planning import planned_visits
    from ai.tests.test_place_route_tools import task as planning_task
    value = planning_task()
    value['observations'].append(dict(tool_name='search_places',
        arguments=dict(query='오동도', region='여수', category=None),
        result=dict(places=[dict(id='isolated:odong', name='오동도')])))
    projected = preview_proposals(value, extracted())
    visits = planned_visits(projected)
    assert any(v['item_id'] == 'new:odong' and v['place_ref'] == 'isolated:odong' for v in visits)


def test_pending_place_survives_a_later_run_without_a_new_proposal():
    from ai.judged_runner import preview_proposals
    from ai.planning import planned_visits
    from ai.tests.test_place_route_tools import task as planning_task
    value = planning_task()
    value['items'].append(dict(id='persisted-new', kind='place', title='오동도', item_version=1))
    value['pending_item_ids'] = ['persisted-new']
    value['observations'].append(dict(tool_name='search_places',
        arguments=dict(query='오동도', region='여수', category=None),
        result=dict(places=[dict(id='isolated:odong', name='오동도')])))
    projected = preview_proposals(value, dict(item_proposals=[], support_observations=[]))
    assert any(v['item_id'] == 'persisted-new' for v in planned_visits(projected))


def test_scoped_request_tracks_one_remaining_target_after_one_completed_call():
    from ai.judged_runner import request_states
    request = dict(request_id='req:m102', intent='place_details', status='resolved',
        source_message_id='m102', owner_id='u1', target_refs=['p1', 'p2'], excluded_refs=['p3'])
    observation = dict(tool_name='get_place_details', arguments=dict(place_ref='p2'),
                       result=dict(place=dict(id='p2')))
    state = request_states([request], [observation])[0]
    assert state['pending_refs'] == ['p1'] and state['completed_refs'] == ['p2']
    assert state['excluded_refs'] == ['p3'] and state['status'] == 'pending'
    assert request['status'] == 'resolved'
    assert request_states([request], [observation, dict(observation,
        arguments=dict(place_ref='p1'), result=dict(place=dict(id='p1')))])[0]['status'] == 'completed'
    saved = dict(request, completed_refs=['p1'], pending_refs=['p2'], status='resolved')
    assert request_states([saved], [observation])[0]['status'] == 'completed'


def test_current_exclusion_retires_an_older_pending_scope_without_changing_its_evidence():
    from ai.judged_runner import superseded_requests
    old = dict(request_id='request:m102:place_details', owner_id='u1', intent='place_details',
               target_refs=['p1', 'p2'], pending_refs=['p2'], status='resolved', evidence={'quote': 'old'})
    new = dict(request_id='request:m103:place_details', owner_id='u1', intent='place_details',
               target_refs=['p1'], excluded_refs=['p2'], status='resolved')
    retired = superseded_requests([old], [new])
    assert retired[0]['status'] == 'superseded' and retired[0]['superseded_by'] == new['request_id']
    assert retired[0]['evidence'] == old['evidence'] and not retired[0]['pending_refs']
    assert old['status'] == 'resolved'
    assert superseded_requests([old], [dict(new, owner_id='u2')]) == []
