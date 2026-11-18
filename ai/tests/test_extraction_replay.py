def test_extraction_case_has_only_its_current_message():
    from ai.eval.extraction_replay import case_task
    case = dict(id='isolated',group='place',text='오동도 가자')
    value = case_task(case)
    assert value['recent_messages'] == [dict(id='isolated',author_id='u1',text='오동도 가자')]
    assert value['items'] == [] and value['observations'] == []

def test_extraction_replay_flags_unexpected_condition_values():
    from ai.eval.extraction_replay import check_case
    case = dict(id='hello',places=[],conditions={})
    result = dict(item_proposals=[],constraint_proposals=[dict(key='return_by',value='12:00',owner_id='u1',source_message_ids=['hello'])],support_observations=[],extraction_report=dict(status='ok'))
    assert 'conditions' in check_case(case,result)

def test_replay_rejects_wrong_source_or_owner():
    from ai.eval.extraction_replay import provenance_issues
    case = dict(id='new')
    result = dict(item_proposals=[],constraint_proposals=[dict(owner_id='u2',source_message_ids=['old'])],support_observations=[])
    assert provenance_issues(case,result) == ['provenance']
