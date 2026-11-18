"""Offline regressions for evidence-aware lookup preparation."""
from ai.auxiliary import _merge, relevant_context
from ai.auxiliary_grounding import canonical_unsupported, ground_batch
from ai.auxiliary_schema import AuxiliaryBatch
from ai.condition_grounding import condition_value
from ai.decision_candidates import build_decision_candidates
from ai.tests.test_auxiliary import analysis, batch, evidence, task


def grounded(value, **raw):
    return ground_batch(AuxiliaryBatch.model_validate(batch(**raw)), value)[0]


def lookup(text, *names, fields=('location',), **extra):
    return dict(intent='place_lookup', evidence=evidence(text), target_names=list(names),
                requested_fields=list(fields), **extra)


def search(*places, query='여수 명소'):
    return dict(id='search:existing', tool_name='search_places', room_id='r',
                arguments=dict(query=query, region='여수', category=None),
                result=dict(places=list(places)), source_refs=['search:existing'])


def place(ref, name, address):
    return dict(id=ref, name=name, address=address, latitude=34.7, longitude=127.7)


def test_budget_survives_an_unrelated_deadline_denial():
    text = '내 예산은 15만원이야. 4시까지 귀가한다는 뜻은 아니야'
    assert condition_value('budget_krw', text) == 150000
    assert condition_value('return_by', text) is None


def test_budget_later_denial_of_same_value_is_not_an_assertion():
    assert condition_value('budget_krw', '내 예산은 15만원이야. 예산이 15만원이라는 뜻은 아니야') is None


def test_clipped_quote_cannot_hide_target_adjacent_negation():
    value = task('한강공원 좋아하지 않아. 엑스포는 좋아.')
    output = grounded(value, support_observations=[dict(
        item_id='hangang', item_version=3, stance='support', evidence=evidence('한강공원 좋아'))])
    assert output['support_observations'] == []


def test_second_pass_omission_preserves_unresolved_field():
    field = dict(field='destination', target_ref='anchor:destination', owner_id='u2',
                 text='도착지는 어디인가요?', source='user')
    first = AuxiliaryBatch.model_validate(batch(analysis=analysis(missing_fields=[field])))
    second = AuxiliaryBatch.model_validate(batch())
    merged = _merge(first, second)
    assert [field.field for field in merged.analysis.missing_fields] == ['destination']


def test_grounded_support_resolves_the_same_sources_open_support_target():
    value = task('한강공원 좋아')
    missing = dict(field='support_target', target_ref=None, owner_id='u2', stance='support',
                   text='어느 장소가 좋았나요?', source='history')
    output = grounded(value, support_observations=[dict(item_id='hangang', item_version=3, stance='support',
                      evidence=evidence('한강공원 좋아'))], analysis=analysis(missing_fields=[missing]))
    assert len(output['support_observations']) == 1
    assert output['analysis']['missing_fields'] == []


def test_history_selection_can_be_found_before_there_are_search_observations():
    text = '아까 내가 고른 두 곳 상세 정보 보여줘'
    value = task(text)
    value['conversation_context'] = [
        dict(id='other', author_id='u1', text='오동도하고 여수엑스포 가자'),
        dict(id='selected', author_id='u2', text='돌산공원하고 자산공원으로 하자'),
        dict(id='unrelated', author_id='u2', text='어제 영화 재미있었어'),
    ]
    initial = dict(intent='place_details', evidence=evidence(text), target_names=[])
    assert [m['id'] for m in relevant_context(value, ['내가 고른 두 곳'], [initial])] == ['selected']


def test_mixed_known_and_new_location_names_prepare_search_then_observed_address():
    text = '돌산공원하고 자산공원 찾아줘'
    value = task(text)
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'))]
    output = grounded(value, analysis=analysis(requests=[lookup(text, '돌산공원', '자산공원')]))
    request = output['analysis']['requests'][0]
    assert request['target_refs'] == ['dolsan']
    assert request['unresolved_target_names'] == ['자산공원']
    assert output['item_proposals'] == output['support_observations'] == []
    first = build_decision_candidates(value, output['analysis'])
    assert [(c['tool_name'], c['arguments']) for c in first['candidates']] == [
        ('search_places', dict(query='자산공원', region='여수', category=None))]
    assert first['candidates'][0]['request_targets'] == [
        dict(request_id=request['request_id'], target_name='자산공원', target_ref=None)]

    # Finishing the selected search leaves the observed value available as a direct response.
    value['pending_requests'] = [dict(request, status='pending', completed_refs=['jasan'])]
    value['observations'].append(search(place('jasan', '자산공원', '여수시 자산공원길'), query='자산공원'))
    followup = build_decision_candidates(value, output['analysis'])['candidates']
    assert len(followup) == 1 and followup[0]['action'] == 'direct'
    assert '여수시 돌산로 3600' in followup[0]['reason']
    assert followup[0]['request_ids'] == [request['request_id']]


def test_mixed_known_and_new_detail_names_prepare_distinct_calls():
    text = '돌산공원하고 자산공원 영업시간 알려줘'
    value = task(text)
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'))]
    output = grounded(value, analysis=analysis(requests=[lookup(
        text, '돌산공원', '자산공원', fields=('opening_hours',))]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [(c['tool_name'], c['arguments']) for c in candidates] == [
        ('get_place_details', dict(place_ref='dolsan')),
        ('search_places', dict(query='자산공원', region='여수', category=None)),
    ]


def test_two_observed_branches_make_an_owned_question_when_detail_lookup_needs_one():
    text = '자산카페 메뉴 가격 알려줘'
    value = task(text)
    value['observations'] = [search(
        place('branch-1', '자산카페', '여수시 자산공원길'),
        place('branch-2', '자산카페', '여수시 중앙로'), query='자산카페')]
    output = grounded(value, analysis=analysis(requests=[lookup(text, '자산카페', fields=('price',))]))
    prepared = build_decision_candidates(value, output['analysis'])
    assert len(prepared['candidates']) == 1
    candidate = prepared['candidates'][0]
    assert candidate['action'] == 'ask'
    assert candidate['question']['target_ref'] == output['analysis']['requests'][0]['request_id']
    assert candidate['question']['owner_id'] == 'u2'
    assert [p['place_ref'] for p in candidate['question']['place_choices']] == ['branch-1', 'branch-2']


def test_pure_cancel_binds_only_the_speakers_matching_pending_request():
    value = task('돌산공원 조회는 취소해줘')
    original = dict(request_id='mine', owner_id='u2', intent='place_lookup', status='pending',
                    target_names=['돌산공원'])
    value['pending_requests'] = [original, dict(original, request_id='theirs', owner_id='u1')]
    raw = lookup(value['recent_messages'][0]['text'], '돌산공원', operation='cancel')
    output = grounded(value, analysis=analysis(requests=[raw]))
    cancellation = output['analysis']['requests'][0]
    assert cancellation['operation'] == 'cancel'
    assert cancellation['cancelled_request_ids'] == ['mine']
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [c['action'] for c in candidates] == ['direct']
    assert candidates[0]['request_ids'] == [cancellation['request_id']]


def test_excluded_transit_mode_is_not_an_unsupported_route_request():
    value = task('대중교통 경로 말고 자동차 경로 찾아줘')
    assert not canonical_unsupported(value)['unsupported']
    value = task('자동차 경로 말고 대중교통 경로 찾아줘')
    assert canonical_unsupported(value)['unsupported_code'] == 'non_car_route'


def test_only_negated_lookup_does_not_authorize_a_search_or_visit():
    value = task('돌산공원 찾아주지 마')
    output = grounded(value, analysis=analysis(requests=[lookup('돌산공원 찾아', '돌산공원')]))
    assert not [r for r in output['analysis']['requests'] if r.get('operation') == 'request']
    assert all(c['action'] != 'tool' for c in build_decision_candidates(value, output['analysis'])['candidates'])


def test_reusing_an_observed_address_requires_the_actual_request_evidence():
    value = task('자산공원 위치가 어디야?')
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'),
                                    place('jasan', '자산공원', '여수시 자산공원길'))]
    output = grounded(value, analysis=analysis(requests=[lookup('자산공원 위치가 어디야?', '자산공원')]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert len(candidates) == 1 and candidates[0]['action'] == 'direct'
    assert '여수시 자산공원길' in candidates[0]['reason']
    assert '돌산로' not in candidates[0]['reason']


def test_unrelated_name_in_same_message_cannot_authorize_a_lookup():
    text = '돌산공원은 좋아. 자산공원 찾아줘'
    value = task(text)
    output = grounded(value, analysis=analysis(requests=[lookup(text, '돌산공원')]))
    assert not any(c['action'] == 'tool' for c in build_decision_candidates(value, output['analysis'])['candidates'])


def test_old_search_in_a_different_room_region_cannot_answer_current_lookup():
    text = '돌산공원 찾아줘'
    value = task(text)
    cache = search(place('other', '돌산공원', '서울시 돌산로'), query='돌산공원')
    cache['arguments']['region'] = '서울'
    value['observations'] = [cache]
    output = grounded(value, analysis=analysis(requests=[lookup(text, '돌산공원')]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [(c['tool_name'], c['arguments']) for c in candidates] == [
        ('search_places', dict(query='돌산공원', region='여수', category=None))]


def test_standalone_cancellation_survives_an_omitted_auxiliary_request():
    value = task('취소해줘')
    value['pending_requests'] = [dict(request_id='mine', owner_id='u2', intent='place_lookup',
                                     status='pending', target_names=['돌산공원'])]
    output = grounded(value)
    assert output['analysis']['requests'][0]['cancelled_request_ids'] == ['mine']


def test_split_lookup_targets_preserve_distinct_request_ids_and_source_order():
    text = '자산공원하고 돌산공원 찾아줘'
    value = task(text)
    raw = [lookup(text, '돌산공원'), lookup(text, '자산공원')]
    output = grounded(value, analysis=analysis(requests=raw))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [c['arguments']['query'] for c in candidates] == ['자산공원', '돌산공원']
    assert len({c['request_ids'][0] for c in candidates}) == 2
    assert [r['request_id'] for r in grounded(value, analysis=analysis(requests=raw))['analysis']['requests']] == [
        r['request_id'] for r in output['analysis']['requests']]


def test_fixed_cost_calculation_has_a_candidate_before_any_visit_is_selected():
    value = task('비용 계산해줘')
    value['config'].update(end_date='2026-11-21', per_person_budget_krw=150000,
                           fixed_costs=[dict(id='transport', category='car', scope='shared', owner_id=None,
                                             description='유류·주차·통행료 포함', unit_price_krw=25000, quantity=1,
                                             subtotal_krw=None, paid=False, evidence_id=None, assumption=None)])
    prepared = build_decision_candidates(value)
    assert [c['tool_name'] for c in prepared['candidates']] == ['calculate_costs']


def test_explicit_car_route_uses_evidence_order_and_current_departure():
    text = '돌산공원에서 자산공원까지 지금 자동차 경로 알려줘'
    value = task(text)
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'),
                                    place('jasan', '자산공원', '여수시 자산공원길'))]
    raw = dict(intent='route_lookup', evidence=evidence(text), target_names=['돌산공원', '자산공원'])
    output = grounded(value, analysis=analysis(requests=[raw]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [(c['tool_name'], c['arguments']) for c in candidates] == [
        ('get_car_route', dict(from_ref='dolsan', to_ref='jasan', departure_at=None))]
    raw['target_names'].reverse()
    reversed_output = grounded(value, analysis=analysis(requests=[raw]))
    assert all(c['tool_name'] != 'get_car_route' for c in build_decision_candidates(value, reversed_output['analysis'])['candidates'])


def test_car_route_can_search_missing_endpoint_before_asking_departure():
    text = '돌산공원에서 자산공원까지 자동차 경로 알려줘'
    value = task(text)
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'))]
    raw = dict(intent='route_lookup', evidence=evidence(text), target_names=['돌산공원', '자산공원'])
    output = grounded(value, analysis=analysis(requests=[raw]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [c['tool_name'] for c in candidates] == ['search_places']
    value['observations'].append(search(place('jasan', '자산공원', '여수시 자산공원길'), query='자산공원'))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert len(candidates) == 1
    assert candidates[0]['question']['field'] == 'route_departure'
    assert candidates[0]['question']['owner_id'] == 'u2'


def test_route_keeps_common_endpoints_when_the_user_excludes_the_transit_mode():
    text = '돌산공원에서 버스정류장까지 지금 대중교통 말고 자동차 경로 알려줘'
    value = task(text)
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'),
                                    place('stop', '버스정류장', '여수시 자산공원길'))]
    raw = dict(intent='route_lookup', evidence=evidence(text), target_names=['돌산공원', '버스정류장'])
    output = grounded(value, analysis=analysis(requests=[raw]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [(c['tool_name'], c['arguments']) for c in candidates] == [
        ('get_car_route', dict(from_ref='dolsan', to_ref='stop', departure_at=None))]


def test_car_route_does_not_reuse_reversed_or_foreign_room_observations():
    text = '돌산공원에서 자산공원까지 지금 자동차 경로 알려줘'
    value = task(text)
    value['observations'] = [search(place('dolsan', '돌산공원', '여수시 돌산로 3600'),
                                    place('jasan', '자산공원', '여수시 자산공원길'))]
    for room, start, end in [('r', 'jasan', 'dolsan'), ('other', 'dolsan', 'jasan')]:
        value['observations'].append(dict(room_id=room, tool_name='get_car_route',
            arguments=dict(from_ref=start, to_ref=end, departure_at=None),
            result=dict(from_ref=start, to_ref=end, duration_seconds=600, evidence_id='fixture:route')))
    raw = dict(intent='route_lookup', evidence=evidence(text), target_names=['돌산공원', '자산공원'])
    output = grounded(value, analysis=analysis(requests=[raw]))
    candidates = build_decision_candidates(value, output['analysis'])['candidates']
    assert [c['arguments'] for c in candidates] == [dict(from_ref='dolsan', to_ref='jasan', departure_at=None)]
