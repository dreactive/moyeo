from fastapi.testclient import TestClient
from backend.app import create_app


def test_cookie_identity_register_and_me():
    with TestClient(create_app(database_path=':memory:')) as client:
        assert client.get('/api/auth/me').status_code == 401
        response = client.post('/api/auth/register', json={'name':'민수','email':'a@example.test','password':'password123'})
        assert response.status_code == 201
        assert client.get('/api/auth/me').json() == response.json()
        assert 'httponly' in response.headers['set-cookie'].lower()


def test_login_logout_revokes_cookie():
    with TestClient(create_app(database_path=':memory:')) as client:
        body = {'name': 'a', 'email': 'a@b.test', 'password': 'password123'}
        client.post('/api/auth/register', json=body)
        assert client.post('/api/auth/logout').status_code == 200
        assert client.get('/api/auth/me').status_code == 401
        assert client.post('/api/auth/login', json={'email': body['email'], 'password': 'wrong'}).status_code == 401
        assert client.post('/api/auth/login', json=body).status_code == 200


def test_create_room_is_member_scoped():
    with TestClient(create_app(database_path=':memory:')) as client:
        client.post('/api/auth/register', json={'name':'a','email':'a@b.test','password':'password123'})
        room = client.post('/api/rooms', json={'title':'여수','start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000})
        assert room.status_code == 201
        assert client.get('/api/rooms/' + room.json()['room_id']).status_code == 200


def test_created_room_can_be_retrieved():
    with TestClient(create_app(database_path=':memory:')) as client:
        client.post('/api/auth/register', json={'name':'a','email':'a@b.test','password':'password123'})
        room = client.post('/api/rooms', json={'title':'trip','start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000}).json()
        assert client.get('/api/rooms/' + room['room_id']).json() == room


def test_four_members_join_and_nonmember_blocked():
    app = create_app(database_path=':memory:')
    with TestClient(app) as owner:
        owner.post('/api/auth/register', json={'name':'one','email':'one@b.test','password':'password123'})
        room = owner.post('/api/rooms', json={'title':'trip','start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000}).json()
        for i in range(2, 5):
            guest = TestClient(app, cookies={})
            guest.post('/api/auth/register', json={'name':str(i),'email':str(i)+'@b.test','password':'password123'})
            assert guest.get('/api/rooms/' + room['room_id']).status_code == 403
            joined = guest.post('/api/rooms/join', json={'invite_code':room['invite_code']})
            assert joined.status_code == 200
        assert len(owner.get('/api/rooms/' + room['room_id']).json()['members']) == 4



def test_join_publishes_members_and_returns_recent_messages():
    app = create_app(database_path=':memory:')
    with TestClient(app) as owner:
        owner.post('/api/auth/register', json={'name':'one','email':'one@b.test','password':'password123'})
        room = owner.post('/api/rooms', json={'title':'trip','start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000}).json()
        room['messages'] = [{'id':str(i)} for i in range(51)]
        app.state.db.put('room:' + room['room_id'], room)
        guest = TestClient(app)
        guest.post('/api/auth/register', json={'name':'two','email':'two@b.test','password':'password123'})
        joined = guest.post('/api/rooms/join', json={'invite_code':room['invite_code']}).json()
        assert len(joined['messages']) == 50
        assert joined['seq'] == 1
        assert app.state.db.get('events:' + room['room_id'])[0]['event'] == 'room.updated'
