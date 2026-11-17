from contextlib import contextmanager
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.adapters.local_ai import LocalAIBridge


@contextmanager
def four_clients(config):
    app = create_app(LocalAIBridge({'model_backend':'fake','provider_mode':'fixture'}), database_path=':memory:')
    with TestClient(app) as owner:
        clients = [owner] + [TestClient(app) for _ in range(3)]
        for index, client in enumerate(clients):
            assert client.post('/api/auth/register', json={'name':str(index),'email':str(index)+'@example.test','password':'integration-pass'}).status_code == 201
        created = owner.post('/api/rooms', json=dict(config,title='Integration trip')).json()
        for client in clients[1:]:
            assert client.post('/api/rooms/join', json={'invite_code':created['invite_code']}).status_code == 200
        try:
            yield clients, '/api/rooms/' + created['room_id']
        finally:
            for client in clients[1:]:
                client.close()


@contextmanager
def existing_clients(room, observations=()):
    app = create_app(LocalAIBridge({'model_backend':'fake','provider_mode':'fixture'}), database_path=':memory:')
    with TestClient(app) as owner:
        clients = [owner] + [TestClient(app) for _ in range(3)]
        app.state.db.put('room:' + room['room_id'], room)
        from backend.services.observations import project_observations
        project_observations(app.state.db, room['room_id'], observations)
        for client, member in zip(clients, room['members']):
            user_id = member['user_id']
            app.state.db.put('user:' + user_id, dict(id=user_id,name=member['name'],email=user_id+'@example.test'))
            app.state.db.put('session:integration-'+user_id, user_id)
            client.cookies.set('session','integration-'+user_id)
        try:
            yield clients, '/api/rooms/' + room['room_id']
        finally:
            for client in clients[1:]:
                client.close()
