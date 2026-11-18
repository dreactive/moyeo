from backend.db import serialized
from backend.services.events import publish_event
from backend.services.rooms import require_room
from datetime import datetime, timezone
from uuid import uuid4


@serialized
def save_message(db, room_id, author_id, text):
    room = require_room(db, room_id, author_id)
    message = dict(id=uuid4().hex, room_id=room_id, seq=len(room['messages'])+1, author_id=author_id, text=text, created_at=datetime.now(timezone.utc).isoformat())
    room['messages'].append(message)
    db.put('room:' + room_id, room)
    publish_event(db, room_id, 'message.created', {'message':message})
    return message
