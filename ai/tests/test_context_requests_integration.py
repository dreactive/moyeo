from unittest.mock import patch
import pytest


async def test_two_requested_places_use_history_then_judge_then_existing_executor():
    from ai.eval.context_requests import case_inputs, ContextAuxiliary, assert_case
    from ai.runtime import create_runtime
    task, catalog = case_inputs()
    runtime = create_runtime(dict(model_backend='fake', provider_mode='fixture', max_decision_rounds=2))
    auxiliary = ContextAuxiliary()
    runtime.auxiliary = auxiliary
    events = []
    async def sink(event):
        events.append(event)
    try:
        with patch('ai.providers.fixture.catalog', return_value=catalog):
            result = await runtime.run(task, sink)
    finally:
        await runtime.aclose()
    assert_case(result, events, auxiliary)


async def test_unselected_place_resumes_from_saved_request_after_a_round_limit():
    from ai.eval.context_requests import case_inputs, ContextAuxiliary
    from ai.runtime import create_runtime
    task, catalog = case_inputs()
    runtime = create_runtime(dict(model_backend='fake', provider_mode='fixture', max_decision_rounds=1))
    auxiliary = ContextAuxiliary()
    runtime.auxiliary = auxiliary
    try:
        with patch('ai.providers.fixture.catalog', return_value=catalog):
            first = await runtime.run(task, None)
            assert len(first['observations']) == 1
            assert first['request_states'][0]['status'] == 'pending'
            assert len(first['request_states'][0]['pending_refs']) == 1
            task['observations'].extend(first['observations'])
            task.update(run_id='later-request', recent_messages=[], conversation_context=[],
                        pending_requests=first['request_states'])
            later = await runtime.run(task, None)
    finally:
        await runtime.aclose()
    assert len(auxiliary.calls) == 2  # saved, already grounded targets need no API reinterpretation
    assert len(later['observations']) == 1
    assert later['observations'][0]['arguments'] != first['observations'][0]['arguments']
    assert later['request_states'][0]['status'] == 'completed'
    assert not later['support_observations']


async def test_new_search_is_not_hidden_by_an_older_scoped_details_request():
    from ai.eval.context_requests import case_inputs, ContextAuxiliary
    from ai.auxiliary_fixture import FixtureAuxiliary
    from ai.runtime import create_runtime
    task, catalog = case_inputs()
    runtime = create_runtime(dict(model_backend='fake', provider_mode='fixture', max_decision_rounds=1))
    runtime.auxiliary = ContextAuxiliary()
    try:
        with patch('ai.providers.fixture.catalog', return_value=catalog):
            first = await runtime.run(task, None)
            task['observations'].extend(first['observations'])
            task.update(pending_requests=first['request_states'], run_id='new-independent',
                        recent_messages=[dict(id='m103', author_id='u1', text='오동도 찾아줘')])
            runtime.auxiliary = FixtureAuxiliary()
            result = await runtime.run(task, None)
    finally:
        await runtime.aclose()
    assert result['observations'][0]['tool_name'] == 'search_places'
    assert result['observations'][0]['arguments']['query'] == '오동도'


@pytest.mark.parametrize('cached', [True, False])
async def test_current_exclusion_cannot_reactivate_the_saved_unselected_place(cached):
    from ai.eval.context_requests import case_inputs, ContextAuxiliary
    from ai.runtime import create_runtime
    task, catalog = case_inputs()
    runtime = create_runtime(dict(model_backend='fake', provider_mode='fixture', max_decision_rounds=1))
    runtime.auxiliary = ContextAuxiliary()
    class CorrectedAuxiliary:
        backend = 'synthetic-correction'
        def extract(self, payload, stage=1):
            message = payload['recent_messages'][0]
            return dict(analysis=dict(summary=message['text'], needs_context=False, context_queries=[],
                missing_fields=[], unsupported=False, unsupported_reason='', direct_text='', noop=False,
                requests=[dict(intent='place_details', evidence=dict(message_id=message['id'], quote=message['text']),
                    target_names=['한밭수목원'], excluded_names=['엑스포과학공원'], context_evidence=[])]))
    try:
        with patch('ai.providers.fixture.catalog', return_value=catalog):
            first = await runtime.run(task, None)
            assert first['request_states'][0]['pending_refs'] == ['p2']
            if cached:
                task['observations'].extend(first['observations'])
            task.update(pending_requests=first['request_states'], run_id='corrected-request',
                recent_messages=[dict(id='m103', author_id='u1', text='엑스포과학공원 말고 한밭수목원 상세 정보 보여줘.')])
            runtime.auxiliary = CorrectedAuxiliary()
            result = await runtime.run(task, None)
    finally:
        await runtime.aclose()
    if cached:
        assert not result['observations']
        assert len(result['candidates'])==1 and result['candidates'][0]['action']=='direct'
        assert '한밭수목원' in result['response']
        assert 'p2' not in result['candidates'][0].get('result_refs', [])
    else:
        assert [o['arguments'] for o in result['observations']] == [dict(place_ref='p1')]
    states = {r['request_id']: r for r in result['request_states']}
    assert states['request:m102:place_details']['status'] == 'superseded'
    assert states['request:m103:place_details']['status'] == 'completed'
