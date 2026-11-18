import pytest


def test_pending_refs_map_to_backend_ids_and_resume_in_next_task(room, agent_result):
    from backend.services.agent_apply import prepare_result
    from backend.services.agent_jobs import make_task
    agent_result.update(item_proposals=[dict(client_ref='pending-new', existing_item_id=None,
        kind='place', title='오동도', source_message_ids=['m4'])], pending_item_ids=['pending-new'],
        constraint_proposals=[], support_observations=[], observations=[], questions=[], conflicts=[], plan_draft=None)
    updated, observations = prepare_result(room, agent_result, [])
    new_id = updated['items'][-1]['id']
    assert new_id != 'pending-new'
    assert updated['agent_pending_item_ids'] == [new_id]
    later = make_task(updated, 'later', 'manual_replan', observations, None)
    assert later['pending_item_ids'] == [new_id]
    assert updated['current_plan'] == room['current_plan']


def test_unknown_pending_ref_is_rejected_before_state_application(room, agent_result):
    from backend.services.agent_apply import prepare_result
    agent_result.update(item_proposals=[], constraint_proposals=[], support_observations=[],
        observations=[], questions=[], conflicts=[], plan_draft=None, pending_item_ids=['missing'])
    with pytest.raises(ValueError, match='pending'):
        prepare_result(room, agent_result, [])


def test_scoped_request_state_resumes_without_registering_historical_votes(room, agent_result):
    from backend.services.agent_apply import prepare_result
    from backend.services.agent_jobs import make_task
    room['messages'].append(dict(id='m102', room_id=room['room_id'], author_id='u1', text='두 곳 상세 정보 보여줘'))
    observations = [dict(tool_name='search_places', arguments=dict(query='공원', region='대전', category=None),
        result=dict(places=[dict(id='p1'), dict(id='p2')]), source_refs=['search-result-1'])]
    state = dict(request_id='request:m102:place_details', intent='place_details', owner_id='u1',
        source_message_id='m102', evidence=dict(message_id='m102', quote='두 곳 상세 정보 보여줘'),
        target_refs=['p1', 'p2'], excluded_refs=[], pending_refs=['p2'], completed_refs=['p1'], status='pending')
    agent_result.update(item_proposals=[], constraint_proposals=[], support_observations=[],
        observations=[], questions=[], conflicts=[], plan_draft=None, request_states=[state])
    updated, _ = prepare_result(room, agent_result, observations)
    later = make_task(updated, 'next', 'manual_replan', observations, None)
    assert later['pending_requests'] == [state]
    assert updated['items'] == room['items']
    agent_result['request_states'] = [dict(state, status='superseded', pending_refs=[], superseded_by='new-request')]
    superseded, _ = prepare_result(updated, agent_result, observations)
    assert make_task(superseded, 'next', 'manual_replan', observations, None)['pending_requests'] == []


def test_scoped_request_state_cannot_impersonate_original_author(room, agent_result):
    from backend.services.agent_apply import prepare_result
    agent_result.update(item_proposals=[], constraint_proposals=[], support_observations=[],
        observations=[], questions=[], conflicts=[], plan_draft=None, request_states=[dict(
            source_message_id='m4', owner_id='u1', target_refs=[], excluded_refs=[], status='needs_input')])
    with pytest.raises(ValueError, match='request'):
        prepare_result(room, agent_result, [])
