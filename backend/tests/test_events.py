def test_event_sequences_and_frames():
    from backend.services.events import publish_event, event_frame
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:r', {'seq':0})
    assert publish_event(db, 'r', 'room.updated', {'changed':['members']}) == 1
    events = db.get('events:r')
    assert events[0]['data']['room_id'] == 'r'
    assert 'id: 1\nevent: room.updated\n' in event_frame(events[0])


def test_stream_replays_only_after_cursor():
    import asyncio
    from backend.services.events import room_event_stream
    from backend.db import Database
    async def scenario():
        db = Database(':memory:')
        db.put('events:r', [{'seq':1,'event':'room.updated','data':{}},{'seq':2,'event':'agent.status','data':{}}])
        stream = room_event_stream(db, 'r', 1)
        assert (await anext(stream)).startswith('id: 2\n')
        await stream.aclose()
    asyncio.run(scenario())
