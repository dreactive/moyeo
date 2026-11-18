
async def test_invalid_schema_is_retried_once_and_not_assisted_into_success():
    from ai.runner import extract_proposals
    from ai.tests.test_place_route_tools import task
    class Broken:
        calls = 0
        def generate_json(self, request):
            self.calls += 1
            return {}
    model = Broken()
    output = await extract_proposals(task(), model, None)
    assert model.calls == 2
    assert output['extraction_report']['status'] == 'failed'
    assert output['constraint_proposals'] == []

async def test_failed_extraction_preserves_watermark_and_never_plans():
    from ai.runner import run_agent
    from ai.tests.test_place_route_tools import task
    class Broken:
        def generate_json(self, request):
            assert request['phase'] == 'extract'
            return {}
    output = await run_agent(task(), Broken(), None, None)
    assert output['extraction_report']['status'] == 'failed'
    assert output['last_processed_message_id'] is None
    assert 'candidates' not in output

def test_unresolved_place_intent_is_not_a_clean_empty_result():
    from ai.extraction_run import extraction_output
    from ai.extraction_schema import ExtractionBatch
    from ai.tests.test_place_route_tools import task
    value = task()
    value['recent_messages'] = [dict(id='new',author_id='u1',text='전남대학교 가자')]
    batch = ExtractionBatch(message_assessments=[dict(message_id='new',intents=['place'])],
                            item_proposals=[],constraint_proposals=[],support_observations=[])
    assert extraction_output(batch,1,None,value)['extraction_report']['status'] == 'filtered'

async def test_runtime_failure_is_not_marked_processed_or_retried():
    from ai.runner import run_agent
    from ai.tests.test_place_route_tools import task
    class Broken:
        calls = 0
        def generate_json(self,request):
            self.calls += 1
            raise RuntimeError('unavailable')
    model = Broken()
    output = await run_agent(task(),model,None,None)
    assert output['last_processed_message_id'] is None
    assert output['extraction_report']['status'] == 'failed'
    assert model.calls == 1
