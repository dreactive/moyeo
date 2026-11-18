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

def test_failed_extraction_persists_only_registered_message_receipts(room, agent_result):
    from backend.db import Database
    from backend.services.agent_apply import apply_agent_result
    db = Database(':memory:')
    db.put('room:' + room['room_id'], room)
    db.put('run:' + agent_result['run_id'],dict(room_id=room['room_id'],base_versions=room['versions'],message_ids=['m4']))
    agent_result['extraction_report'] = dict(status='failed',issue_codes=['ValidationError'],attempts=2,rejected_message_ids=['forged'])
    apply_agent_result(db,agent_result)
    failures = db.get('failed-extraction:' + room['room_id'])
    assert set(failures) == {'m4'}
    assert failures['m4']['status'] == 'retry_required'

def test_manual_recovery_cannot_move_cursor_backwards():
    from backend.services.extraction import latest_processed
    messages = [dict(id=str(index)) for index in range(25)]
    assert latest_processed(messages,'24','3') == '24'
    assert latest_processed(messages,'3','24') == '24'

def test_successful_manual_retry_recovers_receipt_without_cursor_regression(room,agent_result):
    from backend.db import Database
    from backend.services.agent_apply import apply_agent_result
    db = Database(':memory:')
    first,last = room['messages'][0]['id'],room['messages'][-1]['id']
    db.put('room:' + room['room_id'],room)
    db.put('processed-message:' + room['room_id'],last)
    db.put('failed-extraction:' + room['room_id'],{first:dict(status='retry_required')})
    db.put('run:' + agent_result['run_id'],dict(room_id=room['room_id'],base_versions=room['versions'],message_ids=[first]))
    agent_result.update(plan_draft=None,observations=[],last_processed_message_id=first,extraction_report=dict(status='ok',issue_codes=[],rejected_message_ids=[],attempts=1))
    assert apply_agent_result(db,agent_result)
    assert db.get('processed-message:' + room['room_id']) == last
    assert db.get('failed-extraction:' + room['room_id'])[first]['status'] == 'recovered'

def test_queued_empty_message_task_does_not_retry_failed_batch(room, agent_result):
    import asyncio
    from backend.db import Database
    from backend.services.agent_jobs import AgentJobs
    async def scenario():
        class Port:
            calls = 0
            async def run(self,task,emit):
                self.calls += 1
                return dict(agent_result,run_id=task['run_id'],base_versions=task['base_versions'],
                            extraction_report=dict(status='failed',issue_codes=['ValidationError'],attempts=2))
        db = Database(':memory:')
        db.put('room:' + room['room_id'],room)
        port = Port()
        jobs = AgentJobs(db,port)
        await jobs.enqueue(room['room_id'],'new_message')
        await jobs.enqueue(room['room_id'],'new_message')
        worker = asyncio.create_task(jobs.work())
        await asyncio.wait_for(jobs.queue.join(),1)
        worker.cancel()
        assert port.calls == 1
    asyncio.run(scenario())

def test_extraction_status_labels_distinguish_failure_and_filtered_results():
    from backend.services.extraction import extraction_label
    assert '형식' in extraction_label(dict(completion='needs_input',extraction_report=dict(status='failed')))
    assert '근거' in extraction_label(dict(completion='needs_input',extraction_report=dict(status='filtered')))
