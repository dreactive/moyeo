"""Canonical same-owner historical selection scopes actual detail calls."""
from copy import deepcopy
import json
from pathlib import Path


def canonical_task_and_analysis():
    case = json.loads(Path('docs/verification/fixtures/auxiliary-qwen-two-places.json').read_text(encoding='utf-8'))
    current = case['dialogue']['current_message']
    history = case['dialogue']['history']
    seed = case['server_seed']
    observed = seed['existing_search_observation']
    places = [dict(id=p['place_ref'], name=p['name'], latitude=36.3 + n / 1000,
                   longitude=127.3 + n / 1000, provider_refs={'fixture': p['place_ref']})
              for n, p in enumerate(observed['places'])]
    task = dict(run_id='request-scope', room_id=seed['room_id'], goal='new_message', base_versions={'evidence_version': 1},
        recent_messages=[dict(id=current['message_id'], author_id=current['author_id'], text=current['text'])],
        conversation_context=[dict(id=m['message_id'], author_id=m['author_id'], text=m['text']) for m in history],
        members=[dict(user_id='u1'), dict(user_id='u2')], questions=[], constraints=[], current_plan=None,
        config=dict(region=seed['region'], start_date='2026-11-21', end_date='2026-11-22', transport='car',
            origin=dict(latitude=36.3, longitude=127.3), destination=dict(latitude=36.3, longitude=127.3),
            lodging=dict(latitude=36.3, longitude=127.3)),
        items=[dict(id='museum', kind='place', title=places[2]['name'], place_ref='p3', item_version=1,
                    state='supported', supporter_ids=['u1'], opponent_ids=[], source_message_ids=['m101']),
               dict(id='unrelated', kind='place', title='대전동물원', item_version=1, state='mentioned', source_message_ids=[])],
        observations=[dict(id=observed['observation_id'], room_id=seed['room_id'], tool_name='search_places',
            arguments=dict(query='대전 장소', region=seed['region'], category=None), result={'places': places},
            source_refs=[observed['observation_id']])])
    resolved = case['expected_stages']['second_auxiliary']['expected_meaning']
    evidence = resolved['historical_evidence']
    request = dict(request_id='request:m102:place_details', intent='place_details', owner_id='u1', source_message_id='m102',
        evidence=dict(message_id='m102', quote=current['text']), target_names=resolved['target_names'],
        excluded_names=[resolved['historically_excluded_name']], target_refs=['p1', 'p2'], excluded_refs=['p3'],
        context_evidence=[dict(message_id=evidence['message_id'], author_id=evidence['author_id'], quote=evidence[k])
                          for k in ('target_quote', 'exclusion_quote')], status='resolved')
    return task, dict(requests=[request], summary='두 선택 장소의 상세 정보', missing_fields=[], needs_context=False)


def add_details(task, ref):
    place = next(p for p in task['observations'][0]['result']['places'] if p['id'] == ref)
    task['observations'].append(dict(tool_name='get_place_details', arguments={'place_ref': ref},
        result=dict(place=deepcopy(place), menus=[], opening_hours=None, evidence=[]), source_refs=['detail:' + ref]))


def test_canonical_two_place_request_has_exactly_two_detail_candidates_and_no_unrelated_work():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    before = deepcopy(task)
    prepared = build_decision_candidates(task, analysis)
    assert prepared['branch'] == 'valid'
    assert [(c['tool_name'], c['arguments']) for c in prepared['candidates']] == [
        ('get_place_details', {'place_ref': 'p1'}), ('get_place_details', {'place_ref': 'p2'})]
    for candidate in prepared['candidates']:
        assert candidate['action'] == 'tool'
        assert candidate['request_ids'] == ['request:m102:place_details']
        assert candidate['source_message_ids'] == ['m102', 'm101']
        assert 'search-result-1' in candidate['source_refs']
        assert 'p3' not in candidate['source_refs']
    assert not prepared.get('deferred_candidates')
    assert task == before


def test_canonical_scope_retains_only_remaining_target_after_each_actual_detail_observation():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    first = build_decision_candidates(task, analysis)['candidates']
    add_details(task, 'p1')
    remaining = build_decision_candidates(task, analysis)
    assert remaining['branch'] == 'valid'
    assert [(c['tool_name'], c['arguments']) for c in remaining['candidates']] == [('get_place_details', {'place_ref': 'p2'})]
    assert remaining['candidates'][0]['candidate_id'] == first[1]['candidate_id']
    add_details(task, 'p2')
    assert build_decision_candidates(task, analysis) == {'branch': 'invalid', 'candidates': []}
    assert task['items'][1]['title'] == '대전동물원'


def test_unresolved_current_request_never_guesses_detail_targets_or_falls_back_to_pending_tools():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    analysis['requests'][0].update(status='needs_context', target_refs=[], target_names=[], context_evidence=[])
    analysis.update(needs_context=True, context_queries=['내가 고른 두 곳'], direct_text=task['recent_messages'][0]['text'])
    assert build_decision_candidates(task, analysis) == {'branch': 'invalid', 'candidates': []}


def test_request_exclusions_override_a_target_list_and_never_produce_museum_call():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    request = analysis['requests'][0]
    request['target_refs'].append('p3')
    request['target_names'].append('대전시립미술관')
    prepared = build_decision_candidates(task, analysis)
    assert [c['arguments'] for c in prepared['candidates']] == [{'place_ref': 'p1'}, {'place_ref': 'p2'}]


def test_scoped_request_requires_current_owner_and_original_current_and_historical_quotes():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    for changed in ('owner', 'current_quote', 'history_quote', 'history_author', 'unobserved_ref'):
        malformed = deepcopy(analysis)
        request = malformed['requests'][0]
        if changed == 'owner':
            request['owner_id'] = 'u2'
        elif changed == 'current_quote':
            request['evidence']['quote'] = '미술관 상세도 보여줘'
        elif changed == 'history_quote':
            request['context_evidence'][0]['quote'] = '미술관도 선택했다'
        elif changed == 'history_author':
            request['context_evidence'][0]['author_id'] = 'u2'
        else:
            request['target_refs'] = ['invented']
            request['target_names'] = ['한밭수목원']
        assert build_decision_candidates(task, malformed)['candidates'] == [], changed


def test_scoped_observed_reference_must_belong_to_same_room():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    task['observations'][0]['room_id'] = 'other-room'
    assert build_decision_candidates(task, analysis)['candidates'] == []


def test_shared_actual_detail_call_unions_request_ids_and_provenance_without_duplicate_candidates():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    text = '한밭수목원 상세 정보도 보여줘'
    task['recent_messages'].append(dict(id='m103', author_id='u1', text=text))
    analysis['requests'].append(dict(request_id='request:m103:place_details', intent='place_details', owner_id='u1',
        source_message_id='m103', evidence=dict(message_id='m103', quote=text), target_names=['한밭수목원'],
        target_refs=['p1'], excluded_names=[], excluded_refs=[], context_evidence=[], status='resolved'))
    candidates = build_decision_candidates(task, analysis)['candidates']
    assert [c['arguments'] for c in candidates] == [{'place_ref': 'p1'}, {'place_ref': 'p2'}]
    assert candidates[0]['request_ids'] == ['request:m102:place_details', 'request:m103:place_details']
    assert candidates[0]['source_message_ids'] == ['m102', 'm101', 'm103']
    assert candidates[1]['request_ids'] == ['request:m102:place_details']


def test_compact_scoped_context_preserves_historical_author_negation_and_excluded_ref():
    from ai.decision_candidates import build_decision_candidates, compact_decision_context
    task, analysis = canonical_task_and_analysis()
    task['conversation_context'].append(dict(id='unrelated-history', author_id='u2', text='다른 대화'))
    task['observations'][0]['result']['polyline'] = [{'latitude': 1}] * 500
    candidates = build_decision_candidates(task, analysis)['candidates']
    context = compact_decision_context(task, analysis, candidates)
    assert context['requests'][0]['source_message_id'] == 'm102'
    assert context['requests'][0]['owner_id'] == 'u1'
    assert context['requests'][0]['target_refs'] == ['p1', 'p2']
    assert context['requests'][0]['excluded_refs'] == ['p3']
    assert context['requests'][0]['context_evidence'][1] == dict(message_id='m101', author_id='u1', quote='대전시립미술관 말고')
    assert context['source_messages'][0]['id'] == 'm101' and context['source_messages'][0]['author_id'] == 'u1'
    assert context['facts']['places']['p3']['name'] == '대전시립미술관'
    assert context['facts']['place_source_refs']['p1'] == ['search-result-1']
    encoded = json.dumps(context, ensure_ascii=False)
    assert '대전시립미술관 말고' in encoded
    assert '다른 대화' not in encoded and 'polyline' not in encoded
    assert 'observations' not in context
    assert not any(key in context['requests'][0] for key in ('tool_name', 'rank', 'score'))


def test_durable_pending_request_retains_saved_quotes_when_original_messages_leave_context():
    from ai.decision_candidates import build_decision_candidates, compact_decision_context
    task, analysis = canonical_task_and_analysis()
    saved = dict(deepcopy(analysis['requests'][0]), status='pending', pending_refs=['p2'], completed_refs=['p1'])
    task['pending_requests'] = [saved]
    task['recent_messages'], task['conversation_context'] = [], []
    # Persisted completion remains authoritative even if the detail body is not in minimal observations.
    prepared = build_decision_candidates(task, analysis)
    assert [(c['tool_name'], c['arguments']) for c in prepared['candidates']] == [('get_place_details', {'place_ref': 'p2'})]
    assert prepared['candidates'][0]['request_ids'] == ['request:m102:place_details']
    compact = compact_decision_context(task, analysis, prepared['candidates'])
    assert compact['requests'][0]['evidence']['quote'] == '아까 내가 고른 두 곳 상세 정보 보여줘.'
    assert compact['requests'][0]['context_evidence'][1]['quote'] == '대전시립미술관 말고'
    assert compact['requests'][0]['owner_id'] == 'u1'


def test_raw_auxiliary_cannot_authorize_old_unseen_request_by_claiming_it_was_saved():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    task['recent_messages'], task['conversation_context'] = [], []
    analysis['requests'][0]['trusted_saved_request'] = True
    assert build_decision_candidates(task, analysis)['candidates'] == []


def test_changed_pending_request_evidence_or_targets_cannot_use_saved_provenance():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    task['pending_requests'] = [dict(deepcopy(analysis['requests'][0]), status='pending', pending_refs=['p2'], completed_refs=['p1'])]
    task['recent_messages'], task['conversation_context'] = [], []
    for field in ('evidence', 'target_refs', 'excluded_refs'):
        changed = deepcopy(analysis)
        if field == 'evidence':
            changed['requests'][0]['evidence']['quote'] = '박물관 상세 보여줘'
        elif field == 'target_refs':
            changed['requests'][0]['target_refs'] = ['p3']
        else:
            changed['requests'][0]['excluded_refs'] = []
        assert build_decision_candidates(task, changed)['candidates'] == [], field


def test_request_target_order_comes_from_original_evidence_instead_of_auxiliary_list_order():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    request = analysis['requests'][0]
    request['target_refs'].reverse()
    request['target_names'].reverse()
    assert [c['arguments'] for c in build_decision_candidates(task, analysis)['candidates']] == [
        {'place_ref': 'p1'}, {'place_ref': 'p2'}]


def test_request_name_matching_uses_the_same_whitespace_normalization_as_auxiliary_grounding():
    from ai.decision_candidates import build_decision_candidates
    task, analysis = canonical_task_and_analysis()
    analysis['requests'][0]['target_names'][0] = '한밭 수목원'
    assert [c['arguments'] for c in build_decision_candidates(task, analysis)['candidates']] == [
        {'place_ref': 'p1'}, {'place_ref': 'p2'}]
