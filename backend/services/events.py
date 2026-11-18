from backend.db import serialized
import asyncio
import json
from time import monotonic


@serialized
def publish_event(db, room_id, event, payload):
    room = db.get('room:' + room_id)
    room['seq'] += 1
    data = dict(payload, room_id=room_id, seq=room['seq'])
    events = db.get('events:' + room_id) or []
    events.append({'event':event, 'data':data})
    db.put_many({'room:' + room_id:room, 'events:' + room_id:events})
    return room['seq']


def event_frame(event):
    return f"id: {event['data']['seq']}\nevent: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"



async def room_event_stream(db, room_id, after_seq):
    heartbeat_at = monotonic() + 15
    yield ': keepalive\n\n'
    while True:
        for event in db.get('events:' + room_id) or []:
            if event['data']['seq'] > after_seq:
                after_seq = event['data']['seq']
                yield event_frame(event)
        if monotonic() >= heartbeat_at:
            yield ': keepalive\n\n'
            heartbeat_at = monotonic() + 15
        await asyncio.sleep(.15)
