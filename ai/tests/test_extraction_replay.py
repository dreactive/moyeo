def test_extraction_case_has_only_its_current_message():
    from ai.eval.extraction_replay import case_task
    case = dict(id='isolated',group='place',text='오동도 가자')
    value = case_task(case)
    assert value['recent_messages'] == [dict(id='isolated',author_id='u1',text='오동도 가자')]
    assert value['items'] == [] and value['observations'] == []
