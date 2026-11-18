from ai.tests.test_place_route_tools import task


def test_quotes_require_new_message_and_real_substring():
    from ai.grounding import source_message
    value = task()
    evidence = dict(message_id=value['recent_messages'][0]['id'], quote='원문에 없는 말')
    assert source_message(evidence, value) is None
    evidence['quote'] = value['recent_messages'][0]['text']
    assert source_message(evidence, value)['id'] == evidence['message_id']

def test_normalized_place_keeps_original_mention_and_no_new_branch():
    from ai.grounding import project_item
    value = task()
    value['recent_messages'] = [dict(id='new', author_id='u1', text='롤링 파스타에서 점심 먹자')]
    proposal = dict(title='롤링파스타', mention_text='롤링 파스타', existing_item_id=None,
                    evidence=dict(message_id='new', quote='롤링 파스타에서 점심 먹자'))
    assert project_item(proposal, value)['title'] == '롤링파스타'
    proposal['title'] = '롤링파스타 여수점'
    assert project_item(proposal, value) is None

def test_condition_projection_rejects_greeting_hallucination_and_hidden_negation():
    from ai.grounding import project_condition
    value = task()
    value['recent_messages'] = [dict(id='new', author_id='u1', text='안녕')]
    proposal = dict(owner_id='u1', key='return_by', value='12:00', kind='hard',
                    replaces_constraint_id=None, evidence=dict(message_id='new', quote='안녕'))
    assert project_condition(proposal, value) is None
    value['recent_messages'][0]['text'] = '내 예산은 20만원이 아니야'
    proposal.update(key='budget', value=200000, evidence=dict(message_id='new', quote='예산은 20만원'))
    assert project_condition(proposal, value) is None

def test_batch_keeps_valid_place_and_reports_rejected_condition():
    from ai.grounding import ground_extraction
    from ai.extraction_schema import ExtractionBatch
    value = task()
    value['recent_messages'] = [dict(id='new', author_id='u1', text='롤링 파스타에서 점심 먹자')]
    evidence = dict(message_id='new', quote=value['recent_messages'][0]['text'])
    raw = dict(message_assessments=[dict(message_id='new', intents=['place','condition'])],
        item_proposals=[dict(title='롤링 파스타', mention_text='롤링 파스타', existing_item_id=None, evidence=evidence)],
        constraint_proposals=[dict(owner_id='u1', key='return_by', value='12:00', kind='hard', replaces_constraint_id=None, evidence=evidence)], support_observations=[])
    output = ground_extraction(ExtractionBatch.model_validate(raw), value)
    assert len(output.proposals['item_proposals']) == 1
    assert output.proposals['constraint_proposals'] == []
    assert output.rejected_message_ids == ['new']

def test_assessments_cannot_skip_or_duplicate_new_messages():
    import pytest
    from ai.grounding import validate_assessments
    from ai.extraction_schema import ExtractionBatch
    value = task()
    empty = dict(message_assessments=[], item_proposals=[], constraint_proposals=[], support_observations=[])
    with pytest.raises(ValueError, match='assessment'):
        validate_assessments(ExtractionBatch.model_validate(empty), value)

def test_support_keeps_explicit_author_and_item_version():
    from ai.grounding import project_support
    value = task()
    message = next(m for m in value['recent_messages'] if m['id'] == 'm3')
    proposal = dict(item_id='item-b', item_version=1, author_id='u3', stance='support',
                    evidence=dict(message_id='m3', quote=message['text']))
    assert project_support(proposal, value)['source_message_id'] == 'm3'
    proposal['item_version'] = 99
    assert project_support(proposal, value) is None

def test_batch_rejects_missing_assessments_before_projecting():
    import pytest
    from ai.grounding import ground_extraction
    from ai.extraction_schema import ExtractionBatch
    batch = ExtractionBatch(message_assessments=[], item_proposals=[], constraint_proposals=[], support_observations=[])
    with pytest.raises(ValueError, match='assessment'):
        ground_extraction(batch, task())

def test_compact_facts_receive_code_owned_evidence():
    from ai.extraction_projection import facts_to_batch
    value = task()
    value['recent_messages'] = [dict(id='new', author_id='u1', text='오동도 가자')]
    batch = facts_to_batch(dict(places=['오동도'], conditions=[], intents=['place']), value['recent_messages'][0], value)
    assert batch['item_proposals'][0]['evidence'] == dict(message_id='new', quote='오동도 가자')
    assert batch['message_assessments'][0]['message_id'] == 'new'

def test_compact_condition_preserves_owner_and_existing_budget_key():
    from ai.extraction_projection import facts_to_batch
    value = task()
    value['constraints'] = [dict(id='old', owner_id='u1', key='budget')]
    message = dict(id='fix', author_id='u1', text='내 예산은 15만원')
    batch = facts_to_batch(dict(places=[], conditions=[dict(key='budget_krw', value=150000)], intents=['condition']), message, value)
    condition = batch['constraint_proposals'][0]
    assert (condition['owner_id'],condition['key'],condition['replaces_constraint_id']) == ('u1','budget','old')

def test_duplicate_message_places_get_distinct_client_refs():
    from ai.grounding import ground_extraction
    from ai.extraction_schema import ExtractionBatch
    from ai.extraction_projection import facts_to_batch
    value = task()
    message = dict(id='new', author_id='u1', text='오동도랑 전남대학교 가자')
    value['recent_messages'] = [message]
    raw = facts_to_batch(dict(places=['오동도','전남대학교'],conditions=[],intents=['place']),message,value)
    output = ground_extraction(ExtractionBatch.model_validate(raw), value)
    assert len({i['client_ref'] for i in output.proposals['item_proposals']}) == 2

def test_batch_keeps_support_and_asks_about_ambiguous_target():
    from ai.grounding import ground_extraction
    from ai.extraction_schema import ExtractionBatch
    value = task()
    raw = dict(message_assessments=[dict(message_id=m['id'],intents=['support']) for m in value['recent_messages']],
               item_proposals=[],constraint_proposals=[],support_observations=[])
    output = ground_extraction(ExtractionBatch.model_validate(raw),value)
    assert any(s['author_id'] == 'u3' for s in output.proposals['support_observations'])
