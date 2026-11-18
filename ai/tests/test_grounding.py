from ai.tests.test_place_route_tools import task


def test_quotes_require_new_message_and_real_substring():
    from ai.grounding import source_message
    value = task()
    evidence = dict(message_id=value['recent_messages'][0]['id'], quote='원문에 없는 말')
    assert source_message(evidence, value) is None
    evidence['quote'] = value['recent_messages'][0]['text']
    assert source_message(evidence, value)['id'] == evidence['message_id']
