from backend.db import serialized
from backend.services.extraction import select_extraction_messages, extraction_label
from backend.services.agent_apply import apply_agent_result
from backend.services.events import publish_event
from backend.services.observations import get_observations
from backend.services.traces import store_trace
from backend.services.trip_config import agent_config
from fastapi import HTTPException
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
import asyncio


DECISION_FIELDS = ('room_id', 'versions', 'members', 'config', 'constraints', 'items', 'questions',
                   'messages', 'current_plan', 'review_plan', 'confirmed_plan', 'active_target',
                   'confirmations', 'conflicts', 'agent_pending_item_ids', 'agent_requests', 'agent_tool_failures')


@serialized
def decision_snapshot(db, room_id):
    room = db.get('room:' + room_id)
    if room is None:
        return None
    return deepcopy(dict(room={key: room.get(key) for key in DECISION_FIELDS},
                         observations=get_observations(db, room_id)))


def make_task(room, run_id, goal, observations, selection, processed_id=None, failures=None):
    task = {key:room[key] for key in ('room_id','members','config','constraints','items','questions','current_plan')}
    task['config'] = agent_config(task['config'])
    task.update(run_id=run_id, base_versions=room['versions'], goal=goal, recent_messages=select_extraction_messages(room['messages'], processed_id, failures or {}, goal == 'manual_replan'), observations=observations, user_selection=selection)
    first = next((i for i, m in enumerate(room['messages']) if task['recent_messages'] and m['id'] == task['recent_messages'][0]['id']), len(room['messages']))
    task['conversation_context'] = room['messages'][:first][-20:]
    task['pending_item_ids'] = list(room.get('agent_pending_item_ids', []))
    task['pending_requests'] = [r for r in room.get('agent_requests', [])
                                if r.get('status') not in ('completed', 'superseded', 'cancelled', 'unsupported')]
    task['request_history'] = deepcopy(room.get('agent_requests', []))
    task['tool_failures'] = deepcopy(room.get('agent_tool_failures', []))
    return deepcopy(task)



class AgentJobs:
    def __init__(self, db, port):
        self.db, self.port = db, port
        self.queue = asyncio.Queue()
        self.pending = Counter()
        self.pipeline = None
        if callable(getattr(port, 'extract', None)) and callable(getattr(port, 'run_prepared', None)):
            from backend.services.agent_pipeline import PipelineJobs
            self.pipeline = PipelineJobs(db, port)
            self.queue = self.pipeline.queue

    async def enqueue(self, room_id, reason, selection=None):
        if self.pipeline:
            return await self.pipeline.enqueue(room_id, reason, selection)
        with self.db.lock:
            room = self.db.get('room:' + room_id)
            if room is None:
                raise HTTPException(404, 'Room not found')
            task = make_task(room, uuid4().hex, reason, get_observations(self.db, room_id), selection, self.db.get('processed-message:' + room_id), self.db.get('failed-extraction:' + room_id))
            self.register_task(task)
            self.queue.put_nowait(task)
            self.pending[room_id] += 1
        return {key:task[key] for key in ('run_id','base_versions')}

    def refresh_task(self, task):
        with self.db.lock:
            room = self.db.get('room:' + task['room_id'])
            if room is None:
                raise HTTPException(404, 'Room not found')
            if task['user_selection'] and task['base_versions'] != room['versions']:
                raise ValueError('Conflict selection expired')
            fresh = make_task(room, task['run_id'], task['goal'], get_observations(self.db, task['room_id']), task['user_selection'], self.db.get('processed-message:' + task['room_id']), self.db.get('failed-extraction:' + task['room_id']))
            self.register_task(fresh)
            return fresh

    def register_task(self, task):
        record = {key:task[key] for key in ('room_id','base_versions')}
        record['message_ids'] = [message['id'] for message in task['recent_messages']]
        self.db.put('run:' + task['run_id'], record)

    async def requeue_if_idle(self, room_id, reason):
        if self.pending[room_id] != 0:
            return
        try:
            await self.enqueue(room_id, reason)
        except HTTPException as error:
            if error.status_code != 404:
                raise

    async def work(self):
        if self.pipeline:
            await self.pipeline.work()
            return
        while True:
            task = await self.queue.get()
            self.pending[task['room_id']] -= 1
            is_current = None
            try:
                with self.db.lock:
                    task = self.refresh_task(task)
                    snapshot = decision_snapshot(self.db, task['room_id'])
                def is_current(room_id=task['room_id'], expected=snapshot):
                    return decision_snapshot(self.db, room_id) == expected
                if task['goal'] in ('new_message', 'message_created', 'remaining_messages') and not task['recent_messages']:
                    continue
                self.active_run_id = task['run_id']
                set_status(self.db, task['room_id'], task['run_id'], 'running', 'Working')
                if not is_current():
                    await self.requeue_if_idle(task['room_id'], 'state_changed')
                    continue
                run_current = getattr(self.port, 'run_current', None)
                result = await run_current(task, self.emit_trace, is_current) if run_current else await self.port.run(task, self.emit_trace)
                if self.db.get('room:' + task['room_id']) is None:
                    continue
                if (result.get('run_id'), result.get('room_id')) != (task['run_id'], task['room_id']):
                    raise ValueError('Agent result identity does not match the active request')
                with self.db.lock:
                    if self.db.get('room:' + task['room_id']) is None:
                        continue
                    current = is_current()
                    applied = apply_agent_result(self.db, result) if current else False
                    room = self.db.get('room:' + task['room_id'])
                processed = result.get('last_processed_message_id')
                advanced = processed in [message['id'] for message in task['recent_messages']]
                if applied and advanced and select_extraction_messages(room['messages'], self.db.get('processed-message:' + task['room_id']), self.db.get('failed-extraction:' + task['room_id']) or {}) and self.pending[task['room_id']] == 0:
                    await self.requeue_if_idle(task['room_id'], 'remaining_messages')
                if not current and self.pending[task['room_id']] == 0:
                    await self.requeue_if_idle(task['room_id'], 'state_changed')
                elif applied and result.get('decision_report', {}).get('reason')=='round_limit' and self.pending[task['room_id']]==0:
                    await self.requeue_if_idle(task['room_id'], 'continue_pending')
                step = max((event['step'] for event in self.db.traces.get(task['run_id'], {}).get('events', [])), default=0) + 1
                await self.emit_trace(dict(run_id=task['run_id'], step=step, event='state_applied', call_id=None, created_at=datetime.now(timezone.utc).isoformat(), payload={'applied':applied, 'summary':'Applied' if applied else 'Stale result' if not current else 'Extraction failed' if result.get('extraction_report', {}).get('status') == 'failed' else 'Stale result', 'versions':room['versions']}))
                decision = result.get('decision_report', {})
                state = ('done' if applied and result['completion']=='done' else
                         'held' if not current or decision.get('status')=='stale' else
                         'failed' if decision.get('status')=='failed' or result.get('tool_failures') or result.get('extraction_report', {}).get('status')=='failed' else
                         'needs_input' if result.get('questions') else 'waiting')
                set_status(self.db, task['room_id'], task['run_id'], state, extraction_label(result) if current else 'State changed; new decision queued')
            except Exception:
                set_status(self.db, task['room_id'], task['run_id'], 'failed', 'Agent run failed')
                if is_current and not is_current() and self.pending[task['room_id']] == 0:
                    await self.requeue_if_idle(task['room_id'], 'state_changed')
            finally:
                self.queue.task_done()

    async def emit_trace(self, event):
        if event.get('run_id') == self.active_run_id:
            store_trace(self.db, event)





@serialized
def set_status(db, room_id, run_id, state, label):
    room = db.get('room:' + room_id)
    if room is None:
        return
    room['agent_status'] = dict(run_id=run_id, state=state, label=label)
    db.put('room:' + room_id, room)
    publish_event(db, room_id, 'agent.status', {'status':room['agent_status']})


def unprocessed_messages(messages, processed_id):
    start = next((index + 1 for index, message in enumerate(messages) if message['id'] == processed_id), 0)
    return messages[start:start + 20]
