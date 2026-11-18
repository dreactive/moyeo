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
        db.put('events:r', [{'event':'room.updated','data':{'seq':1}},{'event':'agent.status','data':{'seq':2}}])
        stream = room_event_stream(db, 'r', 1)
        assert await anext(stream) == ': keepalive\n\n'
        assert (await anext(stream)).startswith('id: 2\n')
        await stream.aclose()
    asyncio.run(scenario())


def test_events_endpoint_is_authenticated():
    from fastapi.testclient import TestClient
    from backend.app import create_app
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.get('/api/rooms/r/events').status_code == 401


def test_idle_stream_sends_periodic_heartbeat(monkeypatch):
    import asyncio
    import backend.services.events as events
    from backend.db import Database
    clock = [0]
    monkeypatch.setattr(events, 'monotonic', lambda: clock[0], raising=False)
    async def tick(_):
        assert clock[0] < 16, 'idle stream did not emit a heartbeat'
        clock[0] += 1
    monkeypatch.setattr(events.asyncio, 'sleep', tick)
    async def scenario():
        stream = events.room_event_stream(Database(':memory:'), 'r', 4)
        assert await anext(stream) == ': keepalive\n\n'
        clock[0] = 15
        assert await anext(stream) == ': keepalive\n\n'
        await stream.aclose()
    asyncio.run(scenario())
