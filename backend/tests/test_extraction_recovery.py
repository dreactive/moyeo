from backend.services.extraction import select_extraction_messages


def test_failed_twenty_messages_do_not_starve_later_input():
    messages = [dict(id=str(index)) for index in range(21)]
    failures = {str(index):dict(status='retry_required') for index in range(20)}
    assert select_extraction_messages(messages,None,failures) == [messages[20]]
    assert select_extraction_messages(messages,'20',failures,True) == messages[:20]
