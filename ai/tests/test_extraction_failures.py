
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
