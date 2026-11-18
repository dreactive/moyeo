"""Canonical adapter for the user's explicitly synthetic two-place reference case."""
from copy import deepcopy
import json
from pathlib import Path


def fixture_case():
    return json.loads(Path('docs/verification/fixtures/auxiliary-qwen-two-places.json').read_text(encoding='utf-8'))


def case_inputs():
    from ai.providers.fixture import catalog
    case = fixture_case()
    data = deepcopy(catalog())
    places = []
    for index, original in enumerate(case['server_seed']['existing_search_observation']['places']):
        place = dict(id=original['place_ref'], name=original['name'], address='합성 대전 주소',
            latitude=36.37 + index * .01, longitude=127.38 + index * .01,
            source_ref='search-result-1', provider_refs={'fixture': original['place_ref']})
        places.append(place)
        detail = deepcopy(data['details']['fixture:place-a' if index == 0 else 'fixture:place-b'])
        detail['place'] = deepcopy(place)
        data['locations'][place['id']] = deepcopy(place)
        data['details'][place['id']] = detail
    current = case['dialogue']['current_message']
    history = case['dialogue']['history']
    task = dict(room_id='isolated-context-audit', run_id='context-two-places', goal='new_message',
        base_versions=dict(participant_version=1, constraint_version=1, evidence_version=1, plan_revision=0),
        members=[dict(user_id='u1', name='검증 사용자')],
        config=dict(region='대전', start_date='2026-11-21', end_date='2026-11-21', transport='car',
                    origin=None, destination=None, lodging=None),
        recent_messages=[dict(id=current['message_id'], author_id=current['author_id'], text=current['text'])],
        conversation_context=[dict(id=m['message_id'], author_id=m['author_id'], text=m['text']) for m in history],
        items=[], constraints=[], questions=[], current_plan=None, user_selection=None,
        observations=[dict(tool_name='search_places', arguments=dict(query='대전 관광지', region='대전', category=None),
            result=dict(places=places), source_refs=['search-result-1'])])
    return task, data


class ContextAuxiliary:
    backend = 'synthetic-context-audit'

    def __init__(self):
        self.calls = []

    def extract(self, task, stage=1):
        self.calls.append(dict(stage=stage, task=deepcopy(task)))
        current = task['recent_messages'][0]
        analysis = dict(summary=current['text'], needs_context=stage == 1,
            context_queries=['한밭수목원', '엑스포과학공원', '대전시립미술관'] if stage == 1 else [],
            missing_fields=[], unsupported=False, unsupported_reason='', direct_text='', noop=False)
        request = dict(intent='place_details', evidence=dict(message_id=current['id'], quote=current['text']),
                       target_names=[], excluded_names=[], context_evidence=[])
        if stage == 2:
            request.update(target_names=['한밭수목원', '엑스포과학공원'], excluded_names=['대전시립미술관'],
                context_evidence=[dict(message_id='m101', quote='한밭수목원하고 엑스포과학공원으로 하자.'),
                                  dict(message_id='m101', quote='대전시립미술관 말고')])
        analysis['requests'] = [request]
        return dict(item_proposals=[], constraint_proposals=[], support_observations=[], analysis=analysis)


def assert_case(result, events, auxiliary):
    assert [c['stage'] for c in auxiliary.calls] == [1, 2]
    assert 'conversation_context' not in auxiliary.calls[0]['task']
    assert [m['id'] for m in auxiliary.calls[1]['task']['conversation_context']] == ['m101']
    assert auxiliary.calls[1]['task']['first_pass']['analysis']['requests']
    decisions = [e['payload'] for e in events if e['event'] == 'decision' and e['payload'].get('scores')]
    assert len(decisions) == 2
    assert [len(d['candidates']) for d in decisions] == [2, 1]
    assert {c['arguments']['place_ref'] for c in decisions[0]['candidates']} == {'p1', 'p2'}
    executed = result['observations']
    assert len(executed) == 2 and {o['arguments']['place_ref'] for o in executed} == {'p1', 'p2'}
    for decision, observation in zip(decisions, executed):
        selected = decision['candidates'][decision['selected_index']]
        assert selected['tool_name'] == observation['tool_name'] == 'get_place_details'
        assert selected['arguments'] == observation['arguments']
    assert len(decisions[0]['request_states'][0]['pending_refs']) == 2
    assert len(decisions[1]['request_states'][0]['pending_refs']) == 1
    state = result['request_states'][0]
    assert state['status'] == 'completed' and not state['pending_refs']
    assert state['excluded_refs'] == ['p3'] and state['owner_id'] == 'u1'
    assert {e['author_id'] for e in state['context_evidence']} == {'u1'}
    assert not result['item_proposals'] and not result['support_observations']
    assert result['completion'] == 'done'
    assert all(e['payload'].get('execution_source') == 'fixture' for e in events if e['event'] == 'tool_result')
