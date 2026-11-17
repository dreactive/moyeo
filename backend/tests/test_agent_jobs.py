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
                return {'completion':'done'}
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
