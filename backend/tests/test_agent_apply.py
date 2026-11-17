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
