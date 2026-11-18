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

async def test_fake_extraction_replay_reports_actual_selected_fixture_calls():
    from ai.eval.extraction_replay import replay_case
    from ai.runtime import create_runtime
    runtime = create_runtime(dict(model_backend='fake',provider_mode='fixture'))
    try:
        row = await replay_case(runtime,dict(id='island',group='place',text='오동도 가자',places=['오동도'],conditions={}))
    finally:
        await runtime.aclose()
    assert row['passed'] and row['tool_calls'] == 4
    observations = row['result']['observations']
    assert [o['tool_name'] for o in observations] == ['search_places', 'get_car_route', 'get_car_route', 'calculate_costs']
    assert row['result']['partial_results']['calculate_costs']['known_total_krw'] == 80000
    assert row['result']['partial_results']['calculate_costs']['total_krw'] is None
    assert observations[0]['arguments'] == dict(query='오동도', region='여수', category=None)
    assert observations[0]['result']['places'] == []
    assert row['result']['plan_draft'] is None and row['result']['completion'] == 'needs_input'


def test_replay_summary_keeps_quality_failures_visible():
    from ai.eval.extraction_replay import summarize
    rows = [dict(passed=False,critical=True,issues=['conditions'],seconds=1.0,tool_calls=0,result={'extraction_report':{'status':'ok'}})]
    summary = summarize(rows)
    assert summary['passed'] == 0 and summary['unexpected_conditions'] == 1
    assert summary['critical_passed'] is False

def test_generation_measurement_restores_model_method():
    from ai.eval.extraction_replay import collect_generations
    from types import SimpleNamespace
    model = SimpleNamespace(generate=lambda **kwargs: [[0,1,2,3]])
    original = model.generate
    with collect_generations(model) as metrics:
        model.generate(input_ids=SimpleNamespace(shape=(1,2)))
    assert metrics[0]['tokens'] == 2 and model.generate is original

async def test_replay_modes_keep_fake_evidence_labeled():
    from ai.eval.extraction_replay import replay_modes
    from ai.runtime import create_runtime
    runtime = create_runtime(dict(model_backend='fake',provider_mode='fixture'))
    reports = await replay_modes(runtime,[dict(id='hello',group='negative',text='안녕',places=[],conditions={})],['fake'])
    await runtime.aclose()
    assert reports['fake']['summary']['passed'] == 1
