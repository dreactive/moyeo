def test_semantic_hash_ignores_poll_time_and_votes(room):
    from backend.services.planning import semantic_plan_hash
    from copy import deepcopy
    plan = deepcopy(room['current_plan'])
    before = semantic_plan_hash(plan)
    plan.update(retrieved_at='later', supporter_ids=['u1'], agent_status='running')
    assert semantic_plan_hash(plan) == before
    plan['item_snapshots'][0]['title'] = 'changed'
    assert semantic_plan_hash(plan) != before


def test_frozen_target_survives_new_draft(room):
    from backend.services.planning import freeze_review
    from copy import deepcopy
    target = deepcopy(room['current_plan']['confirmation_target'])
    freeze_review(room, target)
    room['current_plan']['plan_revision'] += 1
    room['current_plan']['days'] = []
    freeze_review(room, target)
    assert room['review_plan']['days']
    assert room['active_target'] == target


def test_official_vote_is_unique_and_owned(room):
    from backend.services.planning import record_confirmation
    target = room['current_plan']['confirmation_target']
    record_confirmation(room, 'u1', target, 'confirm')
    record_confirmation(room, 'u1', target, 'confirm')
    assert len(room['confirmations']) == 1
    record_confirmation(room, 'u1', target, 'withdraw')
    assert room['confirmations'][0]['stance'] == 'withdraw'
    assert room['confirmed_plan'] is None


def test_blocking_or_unchecked_requirements_prevent_green(room):
    from backend.services.planning import ready_to_confirm
    plan = room['current_plan']
    assert not ready_to_confirm(room, plan)
    plan['validation'] = 'ready'
    room['constraints'] = []
    assert ready_to_confirm(room, plan)
    plan['blocking_conflict_ids'] = ['blocking']
    assert not ready_to_confirm(room, plan)
    plan['blocking_conflict_ids'] = []
    room['constraints'] = [{'kind':'hard','status':'needs_owner_confirmation'}]
    assert not ready_to_confirm(room, plan)


def test_four_members_same_target_required(room):
    from backend.services.planning import record_confirmation, finalize_plan
    room['current_plan']['validation'] = 'ready'
    room['constraints'] = []
    target = room['current_plan']['confirmation_target']
    for user_id in ('u1','u2','u3'):
        record_confirmation(room, user_id, target, 'confirm')
    assert not finalize_plan(room)
    record_confirmation(room, 'u4', target, 'confirm')
    assert finalize_plan(room)
    assert room['confirmed_plan'] == room['review_plan']
    room['current_plan']['days'] = []
    assert room['confirmed_plan']['days']


def test_explicit_activation_discards_previous_votes(room):
    from backend.services.planning import activate_plan, record_confirmation
    target = room['current_plan']['confirmation_target']
    record_confirmation(room, 'u1', target, 'confirm')
    room['current_plan']['plan_revision'] = 2
    room['current_plan']['confirmation_target'] = dict(target, plan_revision=2)
    activate_plan(room, 2)
    assert room['active_target']['plan_revision'] == 2
    assert room['confirmations'] == []


def test_plan_confirmation_http(api):
    room = api.app.state.db.get('room:room-fixture')
    room['current_plan']['validation'] = 'ready'
    room['constraints'] = []
    api.app.state.db.put('room:room-fixture', room)
    target = room['current_plan']['confirmation_target']
    for i in range(1,5):
        api.cookies.set('session','su'+str(i))
        response = api.post('/api/rooms/room-fixture/plan/confirm', json={'target':target})
        assert response.status_code == 200
        assert (response.json()['confirmed_plan'] is not None) == (i == 4)


def test_http_withdraw_and_activate_clear_only_current_votes(api):
    path = '/api/rooms/room-fixture/plan'
    room = api.get('/api/rooms/room-fixture').json()
    target = room['current_plan']['confirmation_target']
    api.post(path+'/confirm', json={'target':target})
    withdrawn = api.post(path+'/withdraw', json={'target':target})
    assert withdrawn.status_code == 200
    assert withdrawn.json()['confirmations'][0]['stance'] == 'withdraw'
    activated = api.post(path+'/activate', json={'plan_revision':room['current_plan']['plan_revision']})
    assert activated.status_code == 200
    assert activated.json()['confirmations'] == []


def test_new_draft_conflict_does_not_block_frozen_review(room):
    from backend.services.planning import record_confirmation, finalize_plan
    room['constraints'] = []
    room['current_plan']['validation'] = 'ready'
    target = room['current_plan']['confirmation_target']
    record_confirmation(room, 'u1', target, 'confirm')
    room['conflicts'] = [{'id':'new-draft-only','blocking':True,'status':'open'}]
    for actor in ('u2','u3','u4'):
        record_confirmation(room, actor, target, 'confirm')
    assert finalize_plan(room)


def test_withdraw_before_review_does_not_activate_plan(room):
    import pytest
    from fastapi import HTTPException
    from backend.services.planning import record_confirmation
    with pytest.raises(HTTPException):
        record_confirmation(room, 'u1', room['current_plan']['confirmation_target'], 'withdraw')
    assert room['review_plan'] is None

def test_conflict_selection_copies_saved_effect(room):
    from backend.services.planning import select_conflict_option
    room['conflicts'] = [{'id':'c','type':'time','explanation':'Fixture conflict','affected_item_ids':['item-b'],'blocking':True,'status':'open','base_versions':dict(room['versions']),'options':[{'id':'o','requires_owner_id':None,'effect':{'kind':'drop_visit','item_id':'item-b'}}]}]
    selected = select_conflict_option(room, 'c', 'o', 'u1')
    assert selected['effect'] == {'kind':'drop_visit','item_id':'item-b'}
    assert room['confirmations'] == []
    room['versions']['constraint_version'] += 1
    import pytest
    with pytest.raises(Exception):
        select_conflict_option(room, 'c', 'o', 'u1')


def test_confirmation_response_contains_confirmed_item_states(api):
    db = api.app.state.db
    room = db.get('room:room-fixture')
    room['current_plan']['validation'] = 'ready'
    room['constraints'] = []
    db.put('room:room-fixture', room)
    for actor in ('u1','u2','u3','u4'):
        api.cookies.set('session','s'+actor)
        response = api.post('/api/rooms/room-fixture/plan/confirm', json={'target':room['current_plan']['confirmation_target']})
    assert all(item['state'] == 'confirmed' for item in response.json()['items'])


def test_conflict_condition_change_stages_owner_card(room):
    from backend.services.planning import apply_selected_condition
    condition = room['constraints'][0]
    condition['status'] = 'confirmed'
    before = condition['value']
    selection = {'effect':{'kind':'change_constraint','constraint_id':condition['id'],'owner_id':condition['owner_id'],'new_value':150000}}
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        apply_selected_condition(room, selection, 'u4')
    pending = apply_selected_condition(room, selection, condition['owner_id'])
    assert pending['status'] == 'needs_owner_confirmation'
    assert condition['value'] == before


def test_conflict_choice_http_returns_run_without_confirmation(api):
    db = api.app.state.db
    room = db.get('room:room-fixture')
    room['conflicts'] = [{'id':'c','type':'time','explanation':'Fixture conflict','affected_item_ids':['item-b'],'blocking':True,'status':'open','base_versions':dict(room['versions']),'options':[{'id':'o','requires_owner_id':None,'effect':{'kind':'drop_visit','item_id':'item-b'}}]}]
    db.put('room:room-fixture', room)
    response = api.post('/api/rooms/room-fixture/conflicts/c/select', json={'option_id':'o'})
    assert response.status_code == 202
    assert set(response.json()) == {'run_id','base_versions'}
    assert api.get('/api/rooms/room-fixture').json()['confirmations'] == []


def test_confirmed_snapshot_is_appended_to_immutable_history(api):
    db = api.app.state.db
    room = db.get('room:room-fixture')
    room['current_plan']['validation'] = 'ready'
    room['constraints'] = []
    db.put('room:room-fixture', room)
    for actor in ('u1','u2','u3','u4'):
        api.cookies.set('session','s'+actor)
        response = api.post('/api/rooms/room-fixture/plan/confirm', json={'target':room['current_plan']['confirmation_target']})
    assert db.get('confirmed-history:room-fixture') == [response.json()['confirmed_plan']]


def test_conflict_options_cannot_target_foreign_items(room):
    from backend.services.planning import validate_effect
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        validate_effect(room, {'kind':'drop_visit','item_id':'foreign'}, [])
    with pytest.raises(HTTPException):
        validate_effect(room, {'kind':'replace_place','item_id':'item-a','new_place_ref':'foreign'}, [])
    validate_effect(room, {'kind':'drop_visit','item_id':'item-a'}, [])
