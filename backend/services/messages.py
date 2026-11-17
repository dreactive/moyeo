from datetime import datetime, timezone
from uuid import uuid4
from backend.services.events import publish_event
from backend.db import serialized


@serialized
def save_message(db, room_id, author_id, text):
    room = db.get('room:' + room_id)
    message = dict(id=uuid4().hex, room_id=room_id, seq=len(room['messages'])+1, author_id=author_id, text=text, created_at=datetime.now(timezone.utc).isoformat())
    room['messages'].append(message)
    db.put('room:' + room_id, room)
    publish_event(db, room_id, 'message.created', {'message':message})
    return message
