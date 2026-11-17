def test_agent_input_uses_recent_human_state():
    from backend.services.agent_jobs import make_task
    from backend.services.rooms import new_room
    room = new_room({'id':'u','name':'U'}, {'title':'trip'})
    room['room_id'] = 'r'
    room['messages'] = [{'id':str(i)} for i in range(25)]
    task = make_task(room, 'run', 'replan', [], None)
    assert len(task['recent_messages']) == 20
    assert task['base_versions'] == room['versions']
    task['base_versions']['plan_revision'] = 99
    assert room['versions']['plan_revision'] == 0
