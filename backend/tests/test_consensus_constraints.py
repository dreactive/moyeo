def test_support_author_matches_source_message(room):
    from backend.services.consensus import valid_support, support_threshold
    observation = dict(item_id='item-b', item_version=1, author_id='u4', stance='support', source_message_id='m4')
    assert support_threshold(4) == 3
    assert support_threshold(3) == 2
    assert valid_support(room, observation, 'u4')
    assert not valid_support(room, observation, 'u3')
    observation['item_version'] = 0
    assert not valid_support(room, observation, 'u4')


def test_support_is_unique_current_version_majority(room):
    from backend.services.consensus import apply_support
    item = room['items'][1]
    item['supporter_ids'] = []
    observation = dict(item_id='item-b', item_version=1, author_id='u4', stance='support', source_message_id='m4')
    apply_support(room, observation, 'u4')
    apply_support(room, observation, 'u4')
    assert item['supporter_ids'] == ['u4']
    assert item['state'] == 'mentioned'
    observation['stance'] = 'oppose'
    apply_support(room, observation, 'u4')
    assert item['supporter_ids'] == []
    assert item['opponent_ids'] == ['u4']
