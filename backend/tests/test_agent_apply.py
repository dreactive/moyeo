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
