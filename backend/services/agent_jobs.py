from backend.db import serialized
from backend.services.agent_apply import apply_agent_result
from backend.services.events import publish_event
from backend.services.observations import get_observations
from backend.services.traces import store_trace
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import asyncio


def make_task(room, run_id, goal, observations, selection, processed_id=None):
    task = {key:room[key] for key in ('room_id','members','config','constraints','items','questions','current_plan')}
    task.update(run_id=run_id, base_versions=room['versions'], goal=goal, recent_messages=unprocessed_messages(room['messages'], processed_id), observations=observations, user_selection=selection)
    return deepcopy(task)



class AgentJobs:
    def __init__(self, db, port):
        self.db, self.port = db, port
        self.queue = asyncio.Queue()
        self.pending = Counter()

    async def enqueue(self, room_id, reason, selection=None):
        room = self.db.get('room:' + room_id)
        task = make_task(room, uuid4().hex, reason, get_observations(self.db, room_id), selection, self.db.get('processed-message:' + room_id))
        self.register_task(task)
        await self.queue.put(task)
        self.pending[room_id] += 1
        return {key:task[key] for key in ('run_id','base_versions')}

    def refresh_task(self, task):
        room = self.db.get('room:' + task['room_id'])
        if task['user_selection'] and task['base_versions'] != room['versions']:
            raise ValueError('Conflict selection expired')
        fresh = make_task(room, task['run_id'], task['goal'], get_observations(self.db, task['room_id']), task['user_selection'], self.db.get('processed-message:' + task['room_id']))
        self.register_task(fresh)
        return fresh

    def register_task(self, task):
        record = {key:task[key] for key in ('room_id','base_versions')}
        record['message_ids'] = [message['id'] for message in task['recent_messages']]
        self.db.put('run:' + task['run_id'], record)

    async def work(self):
        while True:
            task = await self.queue.get()
            self.pending[task['room_id']] -= 1
            try:
                task = self.refresh_task(task)
                self.active_run_id = task['run_id']
                set_status(self.db, task['room_id'], task['run_id'], 'running', 'Working')
                result = await self.port.run(task, self.emit_trace)
                if (result.get('run_id'), result.get('room_id')) != (task['run_id'], task['room_id']):
                    raise ValueError('Agent result identity does not match the active request')
                applied = apply_agent_result(self.db, result)
                processed = result.get('last_processed_message_id')
                room = self.db.get('room:' + task['room_id'])
                advanced = processed in [message['id'] for message in task['recent_messages']]
                if applied and advanced and unprocessed_messages(room['messages'], processed) and self.pending[task['room_id']] == 0:
                    await self.enqueue(task['room_id'], 'remaining_messages')
                if not applied and self.pending[task['room_id']] == 0 and self.db.get('room:' + task['room_id'])['versions'] != task['base_versions']:
                    await self.enqueue(task['room_id'], 'state_changed')
                step = max((event['step'] for event in self.db.traces.get(task['run_id'], {}).get('events', [])), default=0) + 1
                await self.emit_trace(dict(run_id=task['run_id'], step=step, event='state_applied', call_id=None, created_at=datetime.now(timezone.utc).isoformat(), payload={'applied':applied, 'summary':'Applied' if applied else 'Stale result', 'versions':self.db.get('room:' + task['room_id'])['versions']}))
                state = 'done' if applied and result['completion'] == 'done' else 'needs_input'
                set_status(self.db, task['room_id'], task['run_id'], state, result['completion'])
            except Exception:
                set_status(self.db, task['room_id'], task['run_id'], 'needs_input', 'Agent run failed')
            finally:
                self.queue.task_done()

    async def emit_trace(self, event):
        if event.get('run_id') == self.active_run_id:
            store_trace(self.db, event)





@serialized
def set_status(db, room_id, run_id, state, label):
    room = db.get('room:' + room_id)
    room['agent_status'] = dict(run_id=run_id, state=state, label=label)
    db.put('room:' + room_id, room)
    publish_event(db, room_id, 'agent.status', {'status':room['agent_status']})


def unprocessed_messages(messages, processed_id):
    start = next((index + 1 for index, message in enumerate(messages) if message['id'] == processed_id), 0)
    return messages[start:start + 20]
