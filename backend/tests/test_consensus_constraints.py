def test_support_author_matches_source_message(room):
    from backend.services.consensus import valid_support, support_threshold
    observation = dict(item_id='item-b', item_version=1, author_id='u4', stance='support', source_message_id='m4')
    assert support_threshold(4) == 3
    assert support_threshold(3) == 2
    assert valid_support(room, observation, 'u4')
    assert not valid_support(room, observation, 'u3')
    observation['item_version'] = 0
    assert not valid_support(room, observation, 'u4')
