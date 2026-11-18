import copy

import pytest

from ai.tests.test_judged_runner import task, extracted, Judge, Tools


def test_location_lookup_completes_from_search_without_expensive_details():
    from ai.judged_runner import request_states
    request = dict(request_id='r1',intent='place_lookup',status='resolved',
                   target_names=['오동도'],target_refs=[],excluded_refs=[],requested_fields=['location'])
    observation = dict(tool_name='search_places',arguments=dict(query='오동도',region='여수',category=None),
                       result=dict(places=[dict(id='p1',name='오동도',address='여수')]))
    state = request_states([request],[observation])[0]
    assert state['status']=='completed'
    assert state['completed_refs']==['p1'] and not state['pending_refs']
    assert '오동도' in state['response']


def test_finished_detail_lookup_preserves_unknown_price_as_data_gap():
    from ai.judged_runner import request_states
    request = dict(request_id='r1',intent='place_details',status='resolved',target_refs=['p1'])
    observation = dict(tool_name='get_place_details',arguments=dict(place_ref='p1'),
                       result=dict(place=dict(id='p1',name='공원'),menus=[],opening_hours=None,
                                   missing_fields=['price','opening_hours'],match_status='matched'))
    state=request_states([request],[observation])[0]
    assert state['status']=='completed' and state['missing_fields']==['price','opening_hours']
    assert '미확인' in state['response']


async def test_correction_during_tool_call_trace_prevents_actual_dispatch(monkeypatch):
    from ai.judged_runner import run_judged_agent
    current = True
    async def prepare(*args):
        return copy.deepcopy(extracted())
    monkeypatch.setattr('ai.auxiliary.prepare_auxiliary', prepare)
    async def sink(event):
        nonlocal current
        if event['event'] == 'tool_call':
            current = False
    tools = Tools()
    result = await run_judged_agent(task(), Judge(), tools, sink, object(), lambda: current)
    assert not tools.calls
    assert result['decision_report']['status'] == 'stale'
    assert not result['observations']


async def test_one_failed_independent_search_does_not_stop_remaining_search(monkeypatch):
    from ai.judged_runner import run_judged_agent
    value = task()
    output = extracted()
    output['item_proposals'].append(dict(client_ref='new:expo',kind='place',title='엑스포',source_message_ids=['m-new']))
    async def prepare(*args):
        return copy.deepcopy(output)
    monkeypatch.setattr('ai.auxiliary.prepare_auxiliary', prepare)
    class FailOne(Tools):
        async def execute(self, name, arguments):
            self.calls.append((name,copy.deepcopy(arguments)))
            if arguments['query']=='오동도':
                raise ValueError('not uniquely matched')
            return {'places':[]}
    tools = FailOne()
    result = await run_judged_agent(value, Judge(), tools, None, object(), max_rounds=3)
    assert [args['query'] for _,args in tools.calls] == ['오동도','엑스포']
    assert len(result['observations']) == 1
    assert result['tool_failures'][0]['arguments']['query'] == '오동도'
