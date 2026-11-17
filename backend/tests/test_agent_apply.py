def test_sources_are_room_scoped_and_owned(room):
    from backend.domain import valid_sources
    assert valid_sources(room, ['m4'], 'u4')
    assert not valid_sources(room, ['m4'], 'u1')
    assert not valid_sources(room, ['missing'])
    assert not valid_sources(room, [])


def test_new_item_assigns_backend_id_and_maps_client_ref(room):
    from backend.domain import add_item_proposal
    proposal = {'client_ref':'new-cafe','existing_item_id':None,'kind':'place','title':'Cafe','source_message_ids':['m4']}
    item = add_item_proposal(room, proposal)
    assert item['id'] != 'new-cafe'
    assert item['item_version'] == 1
    assert item['supporter_ids'] == []
    assert item in room['items']


def test_item_changes_clear_previous_version_support(room):
    from backend.domain import update_item_proposal
    item = room['items'][1]
    proposal = {'existing_item_id':item['id'],'kind':'place','title':'Changed park','source_message_ids':['m4']}
    update_item_proposal(room, proposal)
    assert item['item_version'] == 2
    assert item['supporter_ids'] == []
    assert item['state'] == 'mentioned'


def test_client_ref_resolves_to_backend_item(room):
    from backend.domain import apply_item_proposals, resolve_refs
    proposal = dict(client_ref='new', existing_item_id=None, kind='place', title='New cafe', source_message_ids=['m4'])
    refs = apply_item_proposals(room, [proposal])
    assert refs['new'] == room['items'][-1]['id']
    assert resolve_refs({'target_ref':'new','related_item_ids':['new']}, refs) == {'target_ref':refs['new'],'related_item_ids':[refs['new']]}


def test_agent_constraint_proposal_never_confirms_or_impersonates(room):
    from backend.domain import add_constraint_proposal
    proposal = dict(owner_id='u4', key='return_by', value='16:00', kind='hard', source_message_ids=['m4'], replaces_constraint_id=None)
    condition = add_constraint_proposal(room, proposal)
    assert condition['status'] == 'needs_owner_confirmation'
    assert add_constraint_proposal(room, proposal) is None
    proposal['owner_id'] = 'u1'
    import pytest
    with pytest.raises(ValueError):
        add_constraint_proposal(room, proposal)


def test_plan_item_snapshots_copy_current_content(room):
    from backend.services.planning import item_snapshots
    plan = room['current_plan']
    snapshots = item_snapshots(room, plan)
    room['items'][0]['title'] = 'Later edit'
    assert snapshots[0]['title'] != 'Later edit'
    assert snapshots[0]['place_ref'] == 'fixture:place-a'


def test_plan_revision_changes_only_for_content_or_inputs(room):
    from backend.services.planning import build_plan
    from copy import deepcopy
    draft = {key:deepcopy(room['current_plan'][key]) for key in ('selected_item_ids','days','cost','validation','blocking_conflict_ids')}
    first = build_plan(room, draft, [])
    room['current_plan'] = first
    assert build_plan(room, draft, []) == first
    draft['days'][0]['visits'][0]['stay_minutes'] = 80
    second = build_plan(room, draft, [])
    assert second['plan_revision'] == first['plan_revision'] + 1
    assert second['content_hash'] != first['content_hash']


def test_stale_base_versions_not_applied(room):
    from backend.db import Database
    from backend.services.agent_apply import valid_result_base
    db = Database(':memory:')
    db.put('room:' + room['room_id'], room)
    result = dict(run_id='run', room_id=room['room_id'], base_versions=dict(room['versions']))
    assert not valid_result_base(db, result)
    db.put('run:run', {'room_id':room['room_id'], 'base_versions':dict(room['versions'])})
    assert valid_result_base(db, result)
    result['base_versions']['constraint_version'] += 1
    assert not valid_result_base(db, result)
