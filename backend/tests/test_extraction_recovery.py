from backend.services.extraction import select_extraction_messages


def test_failed_twenty_messages_do_not_starve_later_input():
    messages = [dict(id=str(index)) for index in range(21)]
    failures = {str(index):dict(status='retry_required') for index in range(20)}
    assert select_extraction_messages(messages,None,failures) == [messages[20]]
    assert select_extraction_messages(messages,'20',failures,True) == messages[:20]

def test_task_separates_past_context_from_unprocessed_messages():
    from backend.services.agent_jobs import make_task
    from backend.services.rooms import new_room
    room = new_room(dict(id='u',name='U'),dict(title='trip'))
    room['messages'] = [dict(id=str(i)) for i in range(25)]
    value = make_task(room,'run','new_message',[],None,'23')
    assert [m['id'] for m in value['recent_messages']] == ['24']
    assert [m['id'] for m in value['conversation_context']] == [str(i) for i in range(4,24)]

def test_failed_extraction_never_applies_even_with_proposals(room, agent_result):
    from backend.db import Database
    from backend.services.agent_apply import apply_agent_result
    db = Database(':memory:')
    db.put('room:' + room['room_id'], room)
    db.put('run:' + agent_result['run_id'], dict(room_id=room['room_id'],base_versions=room['versions'],message_ids=['m4']))
    agent_result['extraction_report'] = dict(status='failed',issue_codes=['ValidationError'],attempts=2,rejected_message_ids=['m4'])
    assert apply_agent_result(db,agent_result) is False
    assert db.get('room:' + room['room_id']) == room
    assert db.get('processed-message:' + room['room_id']) is None
