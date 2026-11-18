"""Map the user-supplied semantic case to current runtime contracts, never a live API claim."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from ai.tests.test_auxiliary import ScriptedAuxiliary, analysis, batch, evidence

CASE = Path('docs/verification/fixtures/auxiliary-qwen-two-places.json')


def semantic_task():
    case = json.loads(CASE.read_text(encoding='utf-8-sig'))
    current = case['dialogue']['current_message']
    messages = [dict(id=m['message_id'], author_id=m['author_id'], text=m['text']) for m in case['dialogue']['history']]
    seed = case['server_seed']
    places = [dict(id=p['place_ref'], name=p['name'], raw_provider_secret='not-for-model')
              for p in seed['existing_search_observation']['places']]
    return dict(room_id=seed['room_id'], run_id='test-run', goal='new_message',
                recent_messages=[dict(id=current['message_id'], author_id=current['author_id'], text=current['text'])],
                conversation_context=messages, members=[dict(user_id='u1'), dict(user_id='u2')],
                config=dict(region=seed['region'], transport='car'), items=[], constraints=[], questions=[], current_plan=None,
                observations=[dict(id='search-result-1', room_id=seed['room_id'], tool_name='search_places',
                                   arguments=dict(query='대전 명소', region='대전', category=None),
                                   result=dict(places=places, provider_payload='private-full-provider-response'), source_refs=['search-result-1'])])


def request(value, targets=(), excluded=(), context=()):
    current = value['recent_messages'][0]
    return dict(intent='place_details', evidence=evidence(current['text'], current['id']), target_names=list(targets),
                excluded_names=list(excluded), context_evidence=list(context))


def stages(value):
    first_request = request(value)
    first = batch(analysis=analysis(summary='아까 내가 고른 두 곳의 상세 정보', needs_context=True,
                    context_queries=['내가 고른 두 곳'], requests=[first_request],
                    missing_fields=[dict(field='target_places', target_ref=None, text='상세 정보를 볼 두 곳은 어디인가요?', owner_id='u1', source='history')]))
    history = value['conversation_context'][0]
    contexts = [evidence('한밭수목원하고 엑스포과학공원으로 하자.', history['id']), evidence('대전시립미술관 말고', history['id'])]
    second = batch(analysis=analysis(requests=[request(value, ['한밭수목원', '엑스포과학공원'], ['대전시립미술관'], contexts)]))
    return first, second


async def test_user_semantic_case_resolves_two_details_targets_from_only_authors_relevant_history():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    first, second = stages(value)
    value['conversation_context'] += [dict(id='other-author', author_id='u2', text='한밭수목원하고 엑스포과학공원 가자'),
                                      dict(id='unrelated', author_id='u1', text='어제 영화가 재미있었어')]
    auxiliary = ScriptedAuxiliary(first, second)
    result = await prepare_auxiliary(value, auxiliary)
    assert result['extraction_report']['status'] == 'ok'
    assert [stage for stage, _ in auxiliary.calls] == [1, 2]
    minimal = auxiliary.calls[0][1]
    assert minimal['observed_places'] == [dict(place_ref='p1', name='한밭수목원'), dict(place_ref='p2', name='엑스포과학공원'), dict(place_ref='p3', name='대전시립미술관')]
    assert 'conversation_context' not in minimal and 'observations' not in minimal
    assert 'not-for-model' not in json.dumps(minimal) and 'private-full-provider-response' not in json.dumps(minimal)
    completed = auxiliary.calls[1][1]
    assert [m['id'] for m in completed['conversation_context']] == ['m101']
    assert completed['first_pass']['analysis']['requests'][0]['evidence'] == evidence(value['recent_messages'][0]['text'], 'm102')
    resolved = result['analysis']['requests'][0]
    assert resolved['request_id'] == 'request:m102:place_details'
    assert resolved['status'] == 'resolved' and resolved['owner_id'] == 'u1' and resolved['source_message_id'] == 'm102'
    assert resolved['target_refs'] == ['p1', 'p2'] and resolved['excluded_refs'] == ['p3']
    assert resolved['context_evidence'] == [dict(message_id='m101', author_id='u1', quote='한밭수목원하고 엑스포과학공원으로 하자.'),
                                             dict(message_id='m101', author_id='u1', quote='대전시립미술관 말고')]
    assert result['item_proposals'] == result['support_observations'] == result['constraint_proposals'] == []
    assert not result['analysis']['missing_fields']


async def test_unresolved_first_pass_has_no_guessed_observed_place_targets():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    first, _ = stages(value)
    value['conversation_context'] = []
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first))
    pending = result['analysis']['requests'][0]
    assert pending['status'] == 'needs_input' and pending['target_refs'] == [] and pending['excluded_refs'] == []
    assert not result['analysis']['noop'] and not result['support_observations']


@pytest.mark.parametrize('fault', ['wrong_author', 'fabricated_quote', 'ambiguous_name', 'foreign_room', 'excluded_as_target'])
async def test_request_resolution_rejects_unowned_ungrounded_or_ambiguous_place_evidence(fault):
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    first, second = stages(value)
    if fault == 'wrong_author':
        value['conversation_context'][0]['author_id'] = 'u2'
    elif fault == 'fabricated_quote':
        second['analysis']['requests'][0]['context_evidence'][0]['quote'] = '두 곳 모두 확정이다'
    elif fault == 'ambiguous_name':
        value['observations'][0]['result']['places'].append(dict(id='other-p1', name='한밭수목원'))
    elif fault == 'foreign_room':
        value['observations'][0]['room_id'] = 'another-room'
    elif fault == 'excluded_as_target':
        second['analysis']['requests'][0]['target_names'] = ['대전시립미술관', '한밭수목원']
        second['analysis']['requests'][0]['excluded_names'] = []
    auxiliary = ScriptedAuxiliary(first, second)
    result = await prepare_auxiliary(value, auxiliary)
    pending = result['analysis']['requests'][0]
    assert pending['status'] != 'resolved'
    if fault == 'ambiguous_name':
        assert pending['target_refs'] == ['p2']
        assert pending['unresolved_target_names'] == ['한밭수목원']
    else:
        assert not pending['target_refs']
    assert not result['support_observations']


async def test_context_completion_cannot_erase_an_unresolved_first_pass_request():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    first, _ = stages(value)
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, batch()))
    assert len(result['analysis']['requests']) == 1
    assert result['analysis']['requests'][0]['status'] != 'resolved'
    assert not result['analysis']['requests'][0]['target_refs']


async def test_explicit_current_place_names_resolve_without_history_completion():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    value['recent_messages'][0]['text'] = '한밭수목원하고 엑스포과학공원 두 곳 상세 정보 보여줘'
    raw = batch(analysis=analysis(requests=[request(value, ['한밭수목원', '엑스포과학공원'])]))
    auxiliary = ScriptedAuxiliary(raw)
    result = await prepare_auxiliary(value, auxiliary)
    assert result['analysis']['requests'][0]['target_refs'] == ['p1', 'p2']
    assert result['analysis']['requests'][0]['status'] == 'resolved'
    assert len(auxiliary.calls) == 1


async def test_request_with_noncurrent_source_fails_closed_without_history_votes():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    raw = batch(analysis=analysis(requests=[dict(intent='place_details', evidence=evidence(value['conversation_context'][0]['text'], 'm101'),
                                                    target_names=['한밭수목원'], excluded_names=[], context_evidence=[])]))
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert result['extraction_report']['status'] == 'failed'
    assert not result['support_observations']

async def test_truncated_history_quote_cannot_hide_target_adjacent_exclusion():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    first, second = stages(value)
    resolved = second['analysis']['requests'][0]
    resolved.update(target_names=['대전시립미술관', '한밭수목원'], excluded_names=[],
                    context_evidence=[evidence('대전시립미술관', 'm101'), evidence('한밭수목원', 'm101')])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert result['analysis']['requests'][0]['status'] != 'resolved'
    assert not result['analysis']['requests'][0]['target_refs']


async def test_latest_cited_positive_selection_is_not_blocked_by_older_exclusion():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    value['conversation_context'] = [dict(id='old', author_id='u1', text='대전시립미술관 말고 한밭수목원 가자'),
                                     dict(id='latest', author_id='u1', text='대전시립미술관하고 엑스포과학공원 두 곳으로 하자')]
    first, _ = stages(semantic_task())
    second = batch(analysis=analysis(requests=[request(value, ['대전시립미술관', '엑스포과학공원'], [],
             [evidence('대전시립미술관 말고', 'old'), evidence('대전시립미술관하고 엑스포과학공원 두 곳으로 하자', 'latest')])]))
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert result['analysis']['requests'][0]['status'] == 'resolved'
    assert result['analysis']['requests'][0]['target_refs'] == ['p3', 'p2']

async def test_two_requested_names_cannot_resolve_to_one_observed_place_ref():
    from ai.auxiliary import prepare_auxiliary
    value = semantic_task()
    value['observations'][0]['result']['places'][1]['id'] = 'p1'
    first, second = stages(value)
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert result['analysis']['requests'][0]['status'] != 'resolved'
    assert not result['analysis']['requests'][0]['target_refs']
