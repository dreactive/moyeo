def test_messages_are_human_and_monotonic():
    from backend.services.messages import save_message
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:r', {'messages':[], 'seq':0})
    first = save_message(db, 'r', 'u1', 'hello')
    second = save_message(db, 'r', 'u2', 'hello again')
    assert first['author_id'] == 'u1'
    assert second['seq'] == 2
    assert db.get('room:r')['messages'] == [first, second]


def test_message_saved_before_blocked_agent():
    import asyncio
    from fastapi.testclient import TestClient
    from backend.app import create_app
    class Blocked:
        async def run(self, task, emit):
            await asyncio.Event().wait()
        async def aclose(self):
            pass
    with TestClient(create_app(Blocked(), database_path=':memory:')) as client:
        client.post('/api/auth/register', json={'name':'a','email':'a@b.test','password':'password123'})
        room = client.post('/api/rooms', json={'title':'trip','start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000}).json()
        path = '/api/rooms/' + room['room_id'] + '/messages'
        sent = client.post(path, json={'text':'hello'})
        assert sent.status_code == 201
        assert client.get(path).json()['messages'] == [sent.json()]


def test_concurrent_messages_are_not_lost():
    from concurrent.futures import ThreadPoolExecutor
    from backend.services.messages import save_message
    from backend.db import Database
    db = Database(':memory:')
    db.put('room:r', {'messages':[], 'seq':0})
    with ThreadPoolExecutor(4) as pool:
        messages = list(pool.map(lambda i: save_message(db, 'r', str(i), 'hello'), range(12)))
    assert len(db.get('room:r')['messages']) == 12
    assert sorted(message['seq'] for message in messages) == list(range(1,13))
