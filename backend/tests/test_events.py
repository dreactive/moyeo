def test_event_sequences_and_frames():
    from backend.services.events import publish_event, event_frame
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:r', {'seq':0})
    assert publish_event(db, 'r', 'room.updated', {'changed':['members']}) == 1
    events = db.get('events:r')
    assert events[0]['data']['room_id'] == 'r'
    assert 'id: 1\nevent: room.updated\n' in event_frame(events[0])
