from ai.tests.test_place_route_tools import task


def test_quotes_require_new_message_and_real_substring():
    from ai.grounding import source_message
    value = task()
    evidence = dict(message_id=value['recent_messages'][0]['id'], quote='원문에 없는 말')
    assert source_message(evidence, value) is None
    evidence['quote'] = value['recent_messages'][0]['text']
    assert source_message(evidence, value)['id'] == evidence['message_id']

def test_normalized_place_keeps_original_mention_and_no_new_branch():
    from ai.grounding import project_item
    value = task()
    value['recent_messages'] = [dict(id='new', author_id='u1', text='롤링 파스타에서 점심 먹자')]
    proposal = dict(title='롤링파스타', mention_text='롤링 파스타', existing_item_id=None,
                    evidence=dict(message_id='new', quote='롤링 파스타에서 점심 먹자'))
    assert project_item(proposal, value)['title'] == '롤링파스타'
    proposal['title'] = '롤링파스타 여수점'
    assert project_item(proposal, value) is None
