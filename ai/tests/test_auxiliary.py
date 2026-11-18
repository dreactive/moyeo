"""Current-message grounding and bounded context for the external auxiliary."""
from copy import deepcopy
import json
import pytest


def task(text='한강공원 말고 엑스포 가자'):
    return dict(room_id='r', run_id='run', recent_messages=[dict(id='new', author_id='u2', text=text)],
                members=[dict(user_id='u1'), dict(user_id='u2')], config=dict(region='여수', start_date='2026-11-21'),
                items=[dict(id='hangang', item_version=3, title='한강공원')], constraints=[], questions=[],
                observations=[], conversation_context=[], current_plan=None)


def analysis(**values):
    return dict(dict(summary='현재 요청', needs_context=False, context_queries=[], missing_fields=[], unsupported=False,
                     unsupported_reason='', direct_text='', noop=False), **values)


def batch(**values):
    return dict(dict(item_proposals=[], constraint_proposals=[], support_observations=[], analysis=analysis()), **values)


def evidence(quote, message_id='new'):
    return dict(message_id=message_id, quote=quote)


class ScriptedAuxiliary:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []

    def extract(self, value, stage=1):
        self.calls.append((stage, deepcopy(value)))
        return deepcopy(self.outputs[len(self.calls) - 1])


async def test_compound_opinions_keep_target_stance_quote_and_code_owned_author():
    from ai.auxiliary import prepare_auxiliary
    raw = batch(item_proposals=[dict(client_ref='expo', title='엑스포', mention_text='엑스포', existing_item_id=None,
                                     evidence=evidence('엑스포 가자'))],
                support_observations=[dict(item_id='hangang', item_version=3, stance='oppose', evidence=evidence('한강공원 말고')),
                                      dict(item_id='expo', item_version=1, stance='support', evidence=evidence('엑스포 가자'))])
    value = await prepare_auxiliary(task(), ScriptedAuxiliary(raw))
    assert [(s['stance'], s['author_id'], s['source_quote']) for s in value['support_observations']] == [
        ('oppose', 'u2', '한강공원 말고'), ('support', 'u2', '엑스포 가자')]
    assert value['support_observations'][1]['item_id'] == value['item_proposals'][0]['client_ref']
    assert value['extraction_report']['status'] == 'ok'


async def test_one_message_places_get_stable_unique_refs_and_repeated_title_merges():
    from ai.auxiliary import prepare_auxiliary
    value = task('오동도랑 엑스포 가자')
    value['items'] = []
    raw = batch(item_proposals=[dict(client_ref=name, title=name, mention_text=name, existing_item_id=None,
                                     evidence=evidence(value['recent_messages'][0]['text'])) for name in ('오동도', '엑스포', '오동도')])
    first = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    second = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    refs = [p['client_ref'] for p in first['item_proposals']]
    assert len(refs) == len(set(refs)) == 2
    assert refs == [p['client_ref'] for p in second['item_proposals']]


async def test_stage_one_excludes_history_plan_geometry_and_preserves_current_message():
    from ai.auxiliary import prepare_auxiliary
    value = task('엑스포 찾아줘')
    value['conversation_context'] = [dict(id='old', author_id='u1', text='다른 여행')]
    value['current_plan'] = dict(secret_note='old plan', days=[dict(route_legs=[dict(polyline=list(range(1000)))])])
    auxiliary = ScriptedAuxiliary(batch())
    await prepare_auxiliary(value, auxiliary)
    payload = auxiliary.calls[0][1]
    assert payload['recent_messages'] == value['recent_messages']
    assert 'conversation_context' not in payload and 'current_plan' not in payload
    assert 'polyline' not in json.dumps(payload)
    assert payload['config']['region'] == '여수'
    assert len(auxiliary.calls) == 1


async def test_short_answer_uses_one_relevant_context_completion_without_history_effects():
    from ai.auxiliary import prepare_auxiliary
    value = task('응')
    value['items'] = [dict(id='expo', item_version=2, title='엑스포')]
    value['conversation_context'] = [dict(id='unrelated', author_id='u1', text='어제 영화 봤어'),
                                     dict(id='old', author_id='u1', text='엑스포 가자는 데 동의해?')]
    first = batch(analysis=analysis(needs_context=True, context_queries=['엑스포']))
    second = batch(item_proposals=[dict(title='엑스포', mention_text='엑스포', existing_item_id=None,
                                       evidence=evidence('엑스포', 'old'))],
                   support_observations=[dict(item_id='expo', item_version=2, stance='support', evidence=evidence('응'),
                                              context_message_ids=['old'])], analysis=analysis(needs_context=True, context_queries=['더 찾아']))
    auxiliary = ScriptedAuxiliary(first, second)
    result = await prepare_auxiliary(value, auxiliary)
    assert [stage for stage, _ in auxiliary.calls] == [1, 2]
    assert [m['id'] for m in auxiliary.calls[1][1]['conversation_context']] == ['old']
    assert not result['item_proposals']
    assert result['support_observations'][0]['author_id'] == 'u2'
    assert result['support_observations'][0]['source_message_id'] == 'new'
    assert result['support_observations'][0]['item_id'] == 'expo'
    assert result['extraction_report']['context_completion_calls'] == 1


async def test_history_only_condition_and_wrong_member_or_quote_are_filtered():
    from ai.auxiliary import prepare_auxiliary
    value = task('내 예산은 15만원')
    value['conversation_context'] = [dict(id='old', author_id='u1', text='내 예산은 20만원')]
    raw = batch(constraint_proposals=[dict(key='budget_krw', value=200000, evidence=evidence('내 예산은 20만원', 'old')),
                                      dict(key='budget_krw', value=150000, evidence=evidence('내 예산은 15만원'))])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert [(p['owner_id'], p['value'], p['source_message_ids']) for p in result['constraint_proposals']] == [('u2', 150000, ['new'])]
    value['recent_messages'][0]['author_id'] = 'outsider'
    assert not (await prepare_auxiliary(value, ScriptedAuxiliary(raw)))['constraint_proposals']


async def test_condition_value_and_replacement_are_conservative_and_owned():
    from ai.auxiliary import prepare_auxiliary
    value = task('내 예산은 2.5만원')
    value['constraints'] = [dict(id='mine', owner_id='u2', key='budget', status='confirmed'),
                            dict(id='theirs', owner_id='u1', key='budget', status='confirmed')]
    raw = batch(constraint_proposals=[dict(key='budget_krw', value=250000, replaces_constraint_id='theirs', evidence=evidence('내 예산은 2.5만원'))])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert not result['constraint_proposals']
    raw['constraint_proposals'][0].update(value=25000, replaces_constraint_id=None)
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert result['constraint_proposals'][0] == dict(owner_id='u2', key='budget', value=25000, kind='hard',
                                                    replaces_constraint_id='mine', source_message_ids=['new'])


async def test_short_budget_correction_needs_matching_owned_prior_condition():
    from ai.auxiliary import prepare_auxiliary
    value = task('아니 15만원')
    raw = batch(constraint_proposals=[dict(key='budget_krw', value=150000, evidence=evidence('아니 15만원'))])
    assert not (await prepare_auxiliary(value, ScriptedAuxiliary(raw)))['constraint_proposals']
    value['constraints'] = [dict(id='budget', owner_id='u2', key='budget', value=200000, status='confirmed')]
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert result['constraint_proposals'][0]['value'] == 150000
    assert result['constraint_proposals'][0]['replaces_constraint_id'] == 'budget'


@pytest.mark.parametrize('title', ['여수', '여수 가자', '점심'])
async def test_region_or_action_phrase_is_not_new_place(title):
    from ai.auxiliary import prepare_auxiliary
    value = task('여수 가자. 점심 먹자')
    raw = batch(item_proposals=[dict(title=title, mention_text=title, existing_item_id=None, evidence=evidence(title))])
    assert not (await prepare_auxiliary(value, ScriptedAuxiliary(raw)))['item_proposals']


async def test_support_rejects_wrong_version_proxy_and_unbound_short_answer():
    from ai.auxiliary import prepare_auxiliary
    for text, version in [('한강공원 좋아', 99), ('다들 한강공원 좋아했대', 3), ('응', 3)]:
        raw = batch(support_observations=[dict(item_id='hangang', item_version=version, stance='support', evidence=evidence(text))])
        assert not (await prepare_auxiliary(task(text), ScriptedAuxiliary(raw)))['support_observations']


async def test_user_missing_information_does_not_read_history_and_noop_cannot_hide_facts():
    from ai.auxiliary import prepare_auxiliary
    value = task('출발지가 어디였지?')
    value['conversation_context'] = [dict(id='old', author_id='u1', text='비밀 과거')]
    raw = batch(analysis=analysis(needs_context=True, context_queries=[], missing_fields=[
        dict(field='origin', target_ref='anchor:origin', text='출발지는 어디인가요?', owner_id='u2')]))
    auxiliary = ScriptedAuxiliary(raw)
    result = await prepare_auxiliary(value, auxiliary)
    assert len(auxiliary.calls) == 1 and result['analysis']['missing_fields'][0]['field'] == 'origin'
    raw = batch(analysis=analysis(noop=True), item_proposals=[dict(title='엑스포', mention_text='엑스포', evidence=evidence('엑스포'))])
    assert not (await prepare_auxiliary(task('엑스포 가자'), ScriptedAuxiliary(raw)))['analysis']['noop']


async def test_unsupported_and_noop_are_distinct_and_analysis_has_current_sources():
    from ai.auxiliary import prepare_auxiliary
    unsupported = await prepare_auxiliary(task('기차표 결제해줘'), ScriptedAuxiliary(batch(analysis=analysis(
        unsupported=True, unsupported_reason='결제 기능을 제공하지 않습니다.'))))
    assert unsupported['analysis']['unsupported'] and not unsupported['analysis']['noop']
    assert unsupported['analysis']['source_message_ids'] == ['new']
    noop = await prepare_auxiliary(task('안녕'), ScriptedAuxiliary(batch(analysis=analysis(noop=True))))
    assert noop['analysis']['noop'] and not noop['analysis']['unsupported']


async def test_external_failure_never_exposes_secret_or_silently_uses_fixture():
    from ai.auxiliary import prepare_auxiliary
    class Broken:
        def extract(self, value, stage=1):
            raise RuntimeError('https://private.example sk-secret Authorization: Bearer secret')
    result = await prepare_auxiliary(task(), Broken())
    assert result['extraction_report']['status'] == 'failed'
    assert 'sk-secret' not in json.dumps(result) and 'private.example' not in json.dumps(result)
    assert not result['item_proposals'] and not result['analysis']['noop']


async def test_malformed_structured_output_fails_closed():
    from ai.auxiliary import prepare_auxiliary
    result = await prepare_auxiliary(task(), ScriptedAuxiliary(dict(analysis=analysis(), injected_tools=[dict(name='search_places')])))
    assert result['extraction_report']['status'] == 'failed'
    assert not result['item_proposals']


def test_factory_external_credentials_are_lazy_safe_and_never_fixture(monkeypatch, tmp_path):
    from ai.auxiliary import create_auxiliary, AuxiliaryConfigurationError
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('AUX_API_KEY', raising=False)
    external = create_auxiliary(dict(auxiliary_backend='external', aux_model='test-model'))
    with pytest.raises(AuxiliaryConfigurationError, match='OPENAI_API_KEY') as error:
        external.extract(task())
    assert 'sk-' not in str(error.value)
    env = tmp_path / '.env'
    env.write_text('OPENAI_API_KEY=sk-test-only\nAUX_MODEL=test-model\nAUX_BASE_URL=https://example.invalid/v1\n', encoding='utf-8')
    configured = create_auxiliary(dict(auxiliary_backend='external', env_file=str(env)))
    assert configured.model == 'test-model' and configured.base_url == 'https://example.invalid/v1'
    assert 'sk-test-only' not in repr(configured)
    with pytest.raises(ValueError):
        create_auxiliary(dict(auxiliary_backend='unknown'))


async def test_explicit_fixture_extracts_new_place_and_conservative_condition():
    from ai.auxiliary import create_auxiliary, prepare_auxiliary
    value = task('오동도 가자. 내 예산은 15만원')
    result = await prepare_auxiliary(value, create_auxiliary(dict(auxiliary_backend='fixture')))
    assert result['extraction_report']['backend'] == 'fixture'
    assert [p['title'] for p in result['item_proposals']] == ['오동도']
    assert result['constraint_proposals'][0]['value'] == 150000
    assert result['support_observations'][0]['stance'] == 'support'

async def test_condition_quote_must_contain_the_value_not_an_unrelated_clause():
    from ai.auxiliary import prepare_auxiliary
    raw = batch(constraint_proposals=[dict(key='budget_krw', value=150000, evidence=evidence('오동도 가자'))])
    result = await prepare_auxiliary(task('오동도 가자. 내 예산은 15만원'), ScriptedAuxiliary(raw))
    assert not result['constraint_proposals']


async def test_noop_cannot_hide_explicit_request_without_extracted_proposals():
    from ai.auxiliary import prepare_auxiliary
    result = await prepare_auxiliary(task('오동도 찾아줘'), ScriptedAuxiliary(batch(analysis=analysis(noop=True))))
    assert not result['analysis']['noop']


async def test_missing_config_and_anchor_targets_are_normalized():
    from ai.auxiliary import prepare_auxiliary
    raw = batch(analysis=analysis(missing_fields=[dict(field='region', target_ref=None, text='어느 지역인가요?', owner_id='u2'),
                                                 dict(field='origin', target_ref=None, text='출발지는 어디인가요?', owner_id=None)]))
    result = await prepare_auxiliary(task('검색해줘'), ScriptedAuxiliary(raw))
    assert [f['target_ref'] for f in result['analysis']['missing_fields']] == ['config:region', 'anchor:origin']


async def test_indirect_negative_reply_keeps_model_stance_with_bound_question():
    from ai.auxiliary import prepare_auxiliary
    value = task('아니')
    value['conversation_context'] = [dict(id='old', author_id='u1', text='한강공원 가자는 데 동의해?')]
    first = batch(analysis=analysis(needs_context=True, context_queries=['한강공원']))
    second = batch(support_observations=[dict(item_id='hangang', item_version=3, stance='oppose', evidence=evidence('아니'),
                                             context_message_ids=['old'])])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert result['support_observations'][0]['stance'] == 'oppose'


async def test_context_completion_has_bounded_relevant_records_and_retains_first_pass_facts():
    from ai.auxiliary import prepare_auxiliary
    value = task('오동도 가자. 거기는 빼자')
    value['conversation_context'] = [dict(id=f'old-{i}', author_id='u1', text='한강공원 관련 질문 ' + '가' * 1200) for i in range(30)]
    first = batch(item_proposals=[dict(title='오동도', mention_text='오동도', evidence=evidence('오동도 가자'))],
                  analysis=analysis(needs_context=True, context_queries=['한강공원']))
    auxiliary = ScriptedAuxiliary(first, batch())
    result = await prepare_auxiliary(value, auxiliary)
    supplied = auxiliary.calls[1][1]['conversation_context']
    assert 0 < len(supplied) <= 8
    assert sum(len(m['text']) for m in supplied) <= 12000
    assert [p['title'] for p in result['item_proposals']] == ['오동도']


async def test_second_pass_failure_retains_independent_grounded_first_pass_without_raw_error():
    from ai.auxiliary import prepare_auxiliary
    class Partial:
        def extract(self, value, stage=1):
            if stage == 2:
                raise RuntimeError('sk-secret-private')
            return batch(item_proposals=[dict(title='오동도', mention_text='오동도', evidence=evidence('오동도 가자'))],
                         analysis=analysis(needs_context=True, context_queries=['한강공원']))
    value = task('오동도 가자. 거기는 빼자')
    value['conversation_context'] = [dict(id='old', author_id='u1', text='한강공원')]
    result = await prepare_auxiliary(value, Partial())
    assert result['extraction_report']['status'] == 'filtered'
    assert result['extraction_report']['issue_codes'] == ['auxiliary_context_completion_failed']
    assert [p['title'] for p in result['item_proposals']] == ['오동도']
    assert 'sk-secret' not in json.dumps(result)


def test_external_model_and_reasoning_settings_use_canonical_env_with_config_precedence(monkeypatch, tmp_path):
    from ai.auxiliary import create_auxiliary
    for name in ('OPENAI_API_KEY', 'AUX_MODEL', 'AUX_BASE_URL', 'AUX_REASONING_EFFORT'):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / '.env'
    env.write_text('AUX_MODEL=gpt-6-luna\nAUX_REASONING_EFFORT=none\n', encoding='utf-8')
    auxiliary = create_auxiliary(dict(auxiliary_backend='external', env_file=str(env)))
    assert auxiliary.model == 'gpt-6-luna' and auxiliary.reasoning_effort == 'none'
    auxiliary = create_auxiliary(dict(auxiliary_backend='external', env_file=str(env), aux_model='other', aux_reasoning_effort='low'))
    assert auxiliary.model == 'other' and auxiliary.reasoning_effort == 'low'

async def test_known_item_ref_cannot_be_hijacked_by_new_model_client_ref():
    from ai.auxiliary import prepare_auxiliary
    raw = batch(item_proposals=[dict(client_ref='hangang', title='엑스포', mention_text='엑스포', evidence=evidence('엑스포 가자'))],
                support_observations=[dict(item_id='hangang', item_version=3, stance='oppose', evidence=evidence('한강공원 말고'))])
    result = await prepare_auxiliary(task(), ScriptedAuxiliary(raw))
    assert result['support_observations'][0]['item_id'] == 'hangang'


async def test_ambiguous_new_client_alias_never_rebinds_after_third_duplicate():
    from ai.auxiliary import prepare_auxiliary
    value = task('오동도 엑스포 오동도 가자')
    value['items'] = []
    raw = batch(item_proposals=[dict(client_ref='same', title=name, mention_text=name, evidence=evidence(value['recent_messages'][0]['text']))
                                 for name in ('오동도', '엑스포', '오동도')],
                support_observations=[dict(item_id='same', item_version=1, stance='support', evidence=evidence('오동도 가자'))])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert not result['support_observations']


async def test_generic_last_word_is_not_a_known_place_reference():
    from ai.auxiliary import prepare_auxiliary
    value = task('공원 좋아')
    value['items'] = [dict(id='park', item_version=1, title='여수 해변 공원')]
    raw = batch(support_observations=[dict(item_id='park', item_version=1, stance='support', evidence=evidence('공원 좋아'))])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert not result['support_observations']


async def test_support_target_question_owner_must_match_current_source_author():
    from ai.auxiliary import prepare_auxiliary
    raw = batch(analysis=analysis(missing_fields=[dict(field='support_target', target_ref=None,
                text='어느 장소인가요?', owner_id='u1', source_message_ids=['new'])]))
    result = await prepare_auxiliary(task('좋아'), ScriptedAuxiliary(raw))
    assert not result['analysis']['missing_fields']


async def test_obvious_standalone_greeting_skips_auxiliary_and_is_explicit_noop():
    from ai.auxiliary import prepare_auxiliary
    class NeverCalled:
        backend = 'external'
        def extract(self, value, stage=1):
            raise AssertionError('Standalone greeting should not call an external model')
    result = await prepare_auxiliary(task('안녕'), NeverCalled())
    assert result['analysis']['noop'] and result['extraction_report']['status'] == 'ok'
    assert result['extraction_report']['attempts'] == 0

async def test_short_reply_binds_owned_open_question_without_history_completion():
    from ai.auxiliary import prepare_auxiliary
    value = task('응')
    value['questions'] = [dict(id='q-support', field='support_target', target_ref='hangang', owner_id='u2',
                               status='open', text='한강공원 가는 데 찬성하나요?')]
    raw = batch(support_observations=[dict(item_id='hangang', item_version=3, stance='support', evidence=evidence('응'), question_id='q-support')])
    auxiliary = ScriptedAuxiliary(raw)
    result = await prepare_auxiliary(value, auxiliary)
    assert result['support_observations'][0]['source_message_id'] == 'new'
    assert result['support_observations'][0]['author_id'] == 'u2'
    assert len(auxiliary.calls) == 1
    value['questions'][0]['owner_id'] = 'u1'
    assert not (await prepare_auxiliary(value, ScriptedAuxiliary(raw)))['support_observations']


async def test_short_reply_can_bind_earlier_current_message_but_not_future_message():
    from ai.auxiliary import prepare_auxiliary
    value = task('응')
    prior = dict(id='current-prior', author_id='u1', text='한강공원 가자')
    value['recent_messages'].insert(0, prior)
    raw = batch(support_observations=[dict(item_id='hangang', item_version=3, stance='support', evidence=evidence('응'),
                                          context_message_ids=['current-prior'])])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert {(o['author_id'],o['source_message_id']) for o in result['support_observations']} == {
        ('u1','current-prior'),('u2','new')}
    value['recent_messages'].reverse()
    reversed_batch = await prepare_auxiliary(value, ScriptedAuxiliary(raw))
    assert [(o['author_id'],o['source_message_id']) for o in reversed_batch['support_observations']] == [
        ('u1','current-prior')]

async def test_fixture_short_replies_bind_open_question_or_current_new_place():
    from ai.auxiliary import prepare_auxiliary, create_auxiliary
    value = task('응')
    value['questions'] = [dict(id='q-support', field='support_target', target_ref='hangang', owner_id='u2',
                               status='open', text='한강공원 가는 데 찬성하나요?')]
    result = await prepare_auxiliary(value, create_auxiliary(dict(auxiliary_backend='fixture')))
    assert result['support_observations'][0]['question_id'] == 'q-support'
    assert result['extraction_report']['attempts'] == 1
    value['questions'], value['items'] = [], []
    value['recent_messages'].insert(0, dict(id='prior', author_id='u1', text='오동도 가자'))
    result = await prepare_auxiliary(value, create_auxiliary(dict(auxiliary_backend='fixture')))
    assert {s['author_id'] for s in result['support_observations']} == {'u1', 'u2'}
    assert len({s['item_id'] for s in result['support_observations']}) == 1


async def test_stage_two_alias_change_does_not_drop_grounded_first_pass_support():
    from ai.auxiliary import prepare_auxiliary
    value = task('엑스포 가자. 거기는 빼자')
    value['conversation_context'] = [dict(id='old', author_id='u1', text='한강공원 가자')]
    item = dict(title='엑스포', mention_text='엑스포', evidence=evidence('엑스포 가자'))
    first = batch(item_proposals=[dict(item, client_ref='first')], analysis=analysis(needs_context=True, context_queries=['한강공원']),
                  support_observations=[dict(item_id='first', item_version=1, stance='support', evidence=evidence('엑스포 가자'))])
    second = batch(item_proposals=[dict(item, client_ref='second')])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert len(result['support_observations']) == 1
    assert result['support_observations'][0]['item_id'] == result['item_proposals'][0]['client_ref']

@pytest.mark.parametrize('reply,stance,accepted', [('응', 'support', True), ('응', 'oppose', False), ('응', 'withdraw', False),
                                                   ('아니', 'support', False), ('아니', 'oppose', True), ('아니', 'withdraw', False)])
async def test_short_reply_polarity_matches_grounded_positive_proposition(reply, stance, accepted):
    from ai.auxiliary import prepare_auxiliary
    value = task(reply)
    value['conversation_context'] = [dict(id='old', author_id='u1', text='한강공원 가자는 데 동의해?')]
    raw = batch(support_observations=[dict(item_id='hangang', item_version=3, stance=stance, evidence=evidence(reply), context_message_ids=['old'])])
    first = batch(analysis=analysis(needs_context=True, context_queries=['한강공원']))
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, raw))
    assert bool(result['support_observations']) is accepted


@pytest.mark.parametrize('prior,stance,accepted', [('한강공원 가지 말자', 'oppose', True), ('한강공원 가지 말자', 'support', False),
                                                 ('한강공원', 'support', False), ('한강공원 반대하지 않아', 'support', True)])
async def test_short_reply_preserves_negative_proposition_and_rejects_unknown_polarity(prior, stance, accepted):
    from ai.auxiliary import prepare_auxiliary
    value = task('응')
    value['conversation_context'] = [dict(id='old', author_id='u1', text=prior)]
    first = batch(analysis=analysis(needs_context=True, context_queries=['한강공원']))
    second = batch(support_observations=[dict(item_id='hangang', item_version=3, stance=stance,
                   evidence=evidence('응'), context_message_ids=['old'])])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert bool(result['support_observations']) is accepted


@pytest.mark.parametrize('text,stance,accepted', [('한강공원에 반대하지 않아', 'support', True), ('한강공원에 반대하지 않아', 'oppose', False),
                                                ('한강공원 좋아하지 않아', 'support', False), ('한강공원 좋아하지 않아', 'oppose', True)])
async def test_target_specific_negation_keeps_model_stance_without_whole_text_overwrite(text, stance, accepted):
    from ai.auxiliary import prepare_auxiliary
    raw = batch(support_observations=[dict(item_id='hangang', item_version=3, stance=stance, evidence=evidence(text))])
    result = await prepare_auxiliary(task(text), ScriptedAuxiliary(raw))
    assert bool(result['support_observations']) is accepted

async def test_unresolved_history_target_becomes_user_clarification_after_bounded_lookup():
    from ai.auxiliary import prepare_auxiliary, create_auxiliary
    value = task('좋아')
    result = await prepare_auxiliary(value, create_auxiliary(dict(auxiliary_backend='fixture')))
    field = result['analysis']['missing_fields'][0]
    assert field['source'] == 'user' and field['stance'] == 'support'
    assert field['owner_id'] == 'u2' and field['source_message_ids'] == ['new']
    assert not result['analysis']['needs_context']


async def test_named_third_party_opinion_is_not_attributed_to_current_author():
    from ai.auxiliary import prepare_auxiliary
    raw = batch(support_observations=[dict(item_id='hangang', item_version=3, stance='support', evidence=evidence('한강공원 좋아'))])
    result = await prepare_auxiliary(task('철수는 한강공원 좋아'), ScriptedAuxiliary(raw))
    assert not result['support_observations']

@pytest.mark.parametrize('reply,stance', [('거기는 빼자', 'oppose'), ('여기는 제외하자', 'oppose'), ('그건 철회', 'withdraw')])
async def test_demonstrative_reply_is_not_misclassified_as_third_party(reply, stance):
    from ai.auxiliary import prepare_auxiliary
    value = task(reply)
    value['conversation_context'] = [dict(id='old', author_id='u1', text='한강공원 가자')]
    first = batch(analysis=analysis(needs_context=True, context_queries=['한강공원']))
    second = batch(support_observations=[dict(item_id='hangang', item_version=3, stance=stance, evidence=evidence(reply),
                                              context_message_ids=['old'])])
    result = await prepare_auxiliary(value, ScriptedAuxiliary(first, second))
    assert result['support_observations'][0]['stance'] == stance
    assert result['support_observations'][0]['author_id'] == 'u2'
    assert result['support_observations'][0]['source_quote'] == reply


@pytest.mark.parametrize('text', ['오동도 찾아줘', '엑스포 자동차 경로 알려줘', '기차표 예약했어', '예약된 숙소 찾아줘',
                                 '예약한 식당의 위치 알려줘', '결제한 금액 계산해줘', '기차역 근처 식당 검색해줘',
                                 '버스정류장까지 자동차 경로 알려줘', '기차표 예약 안 해도 돼'])
async def test_arbitrary_auxiliary_unsupported_claim_is_rejected_for_supported_or_completed_requests(text):
    from ai.auxiliary import prepare_auxiliary
    raw = batch(analysis=analysis(unsupported=True, unsupported_reason='장소 검색 기능이 없습니다. sk-secret-invented-reason'))
    result = await prepare_auxiliary(task(text), ScriptedAuxiliary(raw))
    assert not result['analysis']['unsupported']
    assert result['analysis']['unsupported_reason'] == ''
    assert 'sk-secret' not in result['analysis']['unsupported_reason']


@pytest.mark.parametrize('text,code,reason', [
    ('기차표 결제해줘', 'transaction', '예약·결제·구매·예매를 직접 처리하는 기능은 제공하지 않습니다.'),
    ('식당 예약해 주세요', 'transaction', '예약·결제·구매·예매를 직접 처리하는 기능은 제공하지 않습니다.'),
    ('입장권 구매해줘', 'transaction', '예약·결제·구매·예매를 직접 처리하는 기능은 제공하지 않습니다.'),
    ('공연 예매해줘', 'transaction', '예약·결제·구매·예매를 직접 처리하는 기능은 제공하지 않습니다.'),
    ('기차로 가는 경로 알려줘', 'non_car_route', '현재 경로 조회는 자동차 이동만 지원합니다.'),
    ('대중교통 경로 찾아줘', 'non_car_route', '현재 경로 조회는 자동차 이동만 지원합니다.'),
    ('엑스포까지 도보 길찾기 해줘', 'non_car_route', '현재 경로 조회는 자동차 이동만 지원합니다.'),
])
async def test_unsupported_reason_is_code_owned_and_tied_to_explicit_current_request(text, code, reason):
    from ai.auxiliary import prepare_auxiliary
    raw = batch(analysis=analysis(unsupported=False, unsupported_reason='ignored-model-reason'))
    result = await prepare_auxiliary(task(text), ScriptedAuxiliary(raw))
    assert result['analysis']['unsupported']
    assert result['analysis']['unsupported_code'] == code
    assert result['analysis']['unsupported_reason'] == reason
    assert result['analysis']['unsupported_source_message_ids'] == ['new']

@pytest.mark.parametrize('text,support', [('가상 A식당 가자', True), ('가상 A식당?', False), ('가상 A식당', False)])
async def test_fixture_preserves_full_named_place_and_passive_mention_has_no_support(text, support):
    from ai.auxiliary import create_auxiliary, prepare_auxiliary
    value = task(text)
    value['items'] = []
    result = await prepare_auxiliary(value, create_auxiliary(dict(auxiliary_backend='fixture')))
    assert [p['title'] for p in result['item_proposals']] == ['가상 A식당']
    assert bool(result['support_observations']) is support


def test_standing_non_car_replan_is_unsupported_by_confirmed_transport_config():
    from ai.auxiliary_grounding import canonical_unsupported
    value = task()
    value.update(recent_messages=[], goal='manual_replan')
    value['config']['transport'] = 'walk'
    result = canonical_unsupported(value)
    assert result == dict(unsupported=True, unsupported_reason='현재 경로 조회는 자동차 이동만 지원합니다.',
                          unsupported_code='non_car_route', source_message_ids=[], source_refs=['config:transport'])
    value['config']['transport'] = 'car'
    assert not canonical_unsupported(value)['unsupported']
