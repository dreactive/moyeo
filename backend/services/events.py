import json


def publish_event(db, room_id, event, payload):
    room = db.get('room:' + room_id)
    room['seq'] += 1
    data = dict(payload, room_id=room_id, seq=room['seq'])
    events = db.get('events:' + room_id) or []
    events.append({'event':event, 'data':data})
    db.put('room:' + room_id, room)
    db.put('events:' + room_id, events)
    return room['seq']


def event_frame(event):
    return f"id: {event['data']['seq']}\nevent: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

import asyncio


async def room_event_stream(db, room_id, after_seq):
    while True:
        for event in db.get('events:' + room_id) or []:
            if event['data']['seq'] > after_seq:
                after_seq = event['data']['seq']
                yield event_frame(event)
        await asyncio.sleep(.15)
