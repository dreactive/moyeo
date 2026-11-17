import pytest


@pytest.fixture
def room():
    import json
    from pathlib import Path
    return json.loads(Path('docs/contracts/examples/room-snapshot.example.json').read_text(encoding='utf-8'))

@pytest.fixture
def api(room):
    from backend.app import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(database_path=':memory:')) as client:
        db = client.app.state.db
        db.put('room:' + room['room_id'], room)
        for member in room['members']:
            user_id = member['user_id']
            db.put('user:' + user_id, dict(id=user_id, name=member['name'], email=user_id+'@example.test'))
            db.put('session:s'+user_id, user_id)
        client.cookies.set('session', 'su1')
        yield client

@pytest.fixture
def agent_result():
    import json
    from pathlib import Path
    return json.loads(Path('docs/contracts/examples/agent-result.example.json').read_text(encoding='utf-8'))
