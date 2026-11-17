from copy import deepcopy


def make_task(room, run_id, goal, observations, selection):
    task = {key:room[key] for key in ('room_id','members','config','constraints','items','questions','current_plan')}
    task.update(run_id=run_id, base_versions=room['versions'], goal=goal, recent_messages=room['messages'][-20:], observations=observations, user_selection=selection)
    return deepcopy(task)

import asyncio
from uuid import uuid4


class AgentJobs:
    def __init__(self, db, port):
        self.db, self.port = db, port
        self.queue = asyncio.Queue()

    async def enqueue(self, room_id, reason, selection=None):
        room = self.db.get('room:' + room_id)
        task = make_task(room, uuid4().hex, reason, self.db.get('observations:' + room_id) or [], selection)
        await self.queue.put(task)
        return {key:task[key] for key in ('run_id','base_versions')}

from backend.services.events import publish_event


def set_status(db, room_id, run_id, state, label):
    room = db.get('room:' + room_id)
    room['agent_status'] = dict(run_id=run_id, state=state, label=label)
    db.put('room:' + room_id, room)
    publish_event(db, room_id, 'agent.status', {'status':room['agent_status']})
