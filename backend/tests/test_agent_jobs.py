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


def test_enqueue_returns_versioned_receipt():
    import asyncio
    from backend.services.agent_jobs import AgentJobs
    from backend.services.rooms import new_room
    from backend.db import Database
    db = Database(':memory:')
    room = new_room({'id':'u','name':'U'}, {'title':'trip'})
    room['room_id'] = 'r'
    db.put('room:r', room)
    jobs = AgentJobs(db, None)
    receipt = asyncio.run(jobs.enqueue('r', 'manual_replan'))
    assert receipt['base_versions'] == room['versions']
    assert jobs.queue.qsize() == 1


def test_status_is_published_without_chat():
    from backend.services.agent_jobs import set_status
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:r', {'seq':0, 'messages':[]})
    set_status(db, 'r', 'run1', 'running', 'Working')
    assert db.get('room:r')['agent_status']['state'] == 'running'
    assert db.get('room:r')['messages'] == []
    assert db.get('events:r')[0]['event'] == 'agent.status'


def test_single_worker_never_overlaps_runs():
    import asyncio
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    from backend.services.rooms import new_room
    async def scenario():
        class Port:
            active = 0
            peak = 0
            async def run(self, task, emit):
                self.active += 1
                self.peak = max(self.peak, self.active)
                await asyncio.sleep(.01)
                self.active -= 1
                return dict(run_id=task['run_id'], room_id=task['room_id'], base_versions=task['base_versions'], constraint_proposals=[], item_proposals=[], support_observations=[], questions=[], conflicts=[], observations=[], plan_draft=None, completion='done', last_processed_message_id=None)
        db = Database(':memory:')
        room = new_room({'id':'u','name':'a'}, {'title':'t'})
        room['room_id'] = 'r'
        db.put('room:r', room)
        port = Port()
        jobs = AgentJobs(db, port)
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue('r', 'replan')
        await jobs.enqueue('r', 'replan')
        await asyncio.wait_for(jobs.queue.join(), 2)
        worker.cancel()
        assert port.peak == 1
        assert db.get('room:r')['agent_status']['state'] == 'done'
    asyncio.run(scenario())


def test_enqueue_registers_run_and_uses_product_observations(room):
    import asyncio
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:room-fixture', room)
    db.observations['room-fixture'] = [{'tool_name':'search_places','arguments':{},'result':{'places':[]}}]
    jobs = AgentJobs(db, None)
    receipt = asyncio.run(jobs.enqueue('room-fixture','replan'))
    task = jobs.queue.get_nowait()
    assert task['observations'] == db.observations['room-fixture']
    assert db.get('run:'+receipt['run_id'])['room_id'] == 'room-fixture'



def test_dequeued_task_refreshes_latest_messages_and_versions(room):
    import asyncio
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:room-fixture', room)
    jobs = AgentJobs(db, None)
    asyncio.run(jobs.enqueue('room-fixture','message_created'))
    task = jobs.queue.get_nowait()
    room['versions']['constraint_version'] += 1
    room['messages'].append(dict(id='new',room_id='room-fixture',author_id='u1',seq=6,text='return by 16:00',created_at='2026-11-18T10:05:00+09:00'))
    db.put('room:room-fixture', room)
    refreshed = jobs.refresh_task(task)
    assert refreshed['recent_messages'][-1]['id'] == 'new'
    assert refreshed['base_versions'] == room['versions']


def test_stale_running_result_requeues_latest_input(room, agent_result):
    import asyncio
    from copy import deepcopy
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    async def scenario():
        db = Database(':memory:')
        db.put('room:room-fixture', room)
        class Port:
            calls = 0
            async def run(self, task, emit):
                self.calls += 1
                if self.calls == 1:
                    updated = db.get('room:room-fixture')
                    updated['versions']['constraint_version'] += 1
                    updated['messages'].append(dict(updated['messages'][-1], id='late', text='return by 16:00'))
                    db.put('room:room-fixture', updated)
                else:
                    assert task['recent_messages'][-1]['id'] == 'late'
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'], base_versions=task['base_versions'], plan_draft=None, observations=[], questions=[], last_processed_message_id=task['recent_messages'][-1]['id'])
                return result
        port = Port()
        jobs = AgentJobs(db, port)
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue('room-fixture','replan')
        await asyncio.wait_for(jobs.queue.join(), 2)
        worker.cancel()
        assert port.calls == 2
    asyncio.run(scenario())


def test_invalid_identity_does_not_trigger_retry_loop(room, agent_result):
    import asyncio
    from copy import deepcopy
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    async def scenario():
        db = Database(':memory:')
        db.put('room:room-fixture', room)
        class Port:
            calls = 0
            async def run(self, task, emit):
                self.calls += 1
                if self.calls > 2:
                    raise ValueError('stop invalid retries')
                result = deepcopy(agent_result)
                result['run_id'] = 'wrong'
                return result
        port = Port()
        jobs = AgentJobs(db, port)
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue('room-fixture','replan')
        await asyncio.wait_for(jobs.queue.join(), 2)
        worker.cancel()
        assert port.calls == 1
    asyncio.run(scenario())


def test_unprocessed_message_batches_preserve_backlog_order():
    from backend.services.agent_jobs import unprocessed_messages
    messages = [{'id':str(i)} for i in range(25)]
    assert [m['id'] for m in unprocessed_messages(messages, None)] == [str(i) for i in range(20)]
    assert [m['id'] for m in unprocessed_messages(messages, '19')] == ['20','21','22','23','24']
    assert unprocessed_messages(messages, '24') == []


def test_new_run_excludes_already_processed_messages(room):
    import asyncio
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:room-fixture', room)
    db.put('processed-message:room-fixture','m3')
    jobs = AgentJobs(db, None)
    asyncio.run(jobs.enqueue('room-fixture','message_created'))
    assert [message['id'] for message in jobs.queue.get_nowait()['recent_messages']] == ['m4']


def test_worker_drains_more_than_twenty_unprocessed_messages(room, agent_result):
    import asyncio
    from copy import deepcopy
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    async def scenario():
        db = Database(':memory:')
        room['messages'] = [dict(room['messages'][0],id=str(index),seq=index+1) for index in range(25)]
        db.put('room:room-fixture', room)
        class Port:
            batches = []
            async def run(self, task, emit):
                self.batches.append([m['id'] for m in task['recent_messages']])
                result = deepcopy(agent_result)
                result.update(run_id=task['run_id'],base_versions=task['base_versions'],plan_draft=None,observations=[],questions=[],last_processed_message_id=task['recent_messages'][-1]['id'])
                return result
        port = Port()
        jobs = AgentJobs(db, port)
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue('room-fixture','message_created')
        await asyncio.wait_for(jobs.queue.join(),2)
        worker.cancel()
        assert [len(batch) for batch in port.batches] == [20,5]
        assert db.get('processed-message:room-fixture') == '24'
    asyncio.run(scenario())


def test_worker_rejects_another_registered_run_result(room, agent_result):
    import asyncio
    from copy import deepcopy
    from backend.services.agent_jobs import AgentJobs
    from backend.db import Database
    async def scenario():
        db = Database(':memory:')
        db.put('room:room-fixture', room)
        db.put('run:older', {'room_id':'room-fixture','base_versions':dict(room['versions'])})
        class Port:
            async def run(self, task, emit):
                result = deepcopy(agent_result)
                result.update(run_id='older', completion='done')
                return result
        jobs = AgentJobs(db, Port())
        worker = asyncio.create_task(jobs.work())
        await jobs.enqueue('room-fixture','replan')
        await asyncio.wait_for(jobs.queue.join(),2)
        worker.cancel()
        assert not db.get('run:older').get('applied')
        assert db.get('room:room-fixture')['agent_status']['state'] == 'needs_input'
    asyncio.run(scenario())
