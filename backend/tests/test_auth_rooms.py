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


def test_trip_patch_invalidates_review_and_preserves_history():
    app = create_app(database_path=':memory:')
    with TestClient(app) as client:
        client.post('/api/auth/register', json={'name':'a','email':'a@b.test','password':'password123'})
        room = client.post('/api/rooms', json={'title':'trip','start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000}).json()
        path = '/api/rooms/' + room['room_id']
        revised = client.patch(path + '/trip', json={'per_person_budget_krw':150000})
        assert revised.status_code == 200
        assert revised.json()['config']['per_person_budget_krw'] == 150000
        assert revised.json()['versions']['constraint_version'] == 1


def test_my_rooms_lists_only_member_rooms_with_latest_first():
    with TestClient(create_app(database_path=':memory:')) as owner, TestClient(owner.app) as other:
        assert owner.get('/api/rooms').status_code == 401
        owner.post('/api/auth/register', json={'name':'민수','email':'m@b.test','password':'password123'})
        other.post('/api/auth/register', json={'name':'지수','email':'j@b.test','password':'password123'})
        config = {'start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000}
        first = owner.post('/api/rooms', json={'title':'첫 방', **config}).json()
        second = owner.post('/api/rooms', json={'title':'둘째 방', **config}).json()
        hidden = other.post('/api/rooms', json={'title':'남의 방', **config}).json()
        owner.post('/api/rooms/' + first['room_id'] + '/messages', json={'text':'가상 A식당 가자'})
        rooms = owner.get('/api/rooms').json()['rooms']
        assert [room['title'] for room in rooms] == ['첫 방', '둘째 방']
        assert rooms[0]['last_message']['text'] == '가상 A식당 가자' and rooms[0]['last_message']['mine'] is True
        assert rooms[1]['last_message'] is None and rooms[1]['plan_stage'] == 'empty'
        assert rooms[0]['members'] == [{'user_id': first['members'][0]['user_id'], 'name': '민수'}]
        assert 'messages' not in rooms[0] and 'constraints' not in rooms[0]
        other.post('/api/rooms/join', json={'invite_code': second['invite_code']})
        assert {room['title'] for room in other.get('/api/rooms').json()['rooms']} == {'둘째 방', '남의 방'}
        assert hidden['room_id'] not in [room['room_id'] for room in owner.get('/api/rooms').json()['rooms']]


def test_room_can_start_without_settings_and_invite_by_email():
    with TestClient(create_app(database_path=':memory:')) as owner, TestClient(owner.app) as friend, TestClient(owner.app) as stranger:
        owner.post('/api/auth/register', json={'name':'민수','email':'m@b.test','password':'password123'})
        friend.post('/api/auth/register', json={'name':'지수','email':'j@b.test','password':'password123'})
        stranger.post('/api/auth/register', json={'name':'남','email':'s@b.test','password':'password123'})
        created = owner.post('/api/rooms', json={})
        assert created.status_code == 201
        room = created.json()
        assert room['title'] == '민수의 여행방'
        assert room['config']['start_date'] is None and room['config']['per_person_budget_krw'] is None
        assert room['agent_status']['label'] == '대기'
        path = '/api/rooms/' + room['room_id'] + '/members'
        invited = owner.post(path, json={'email':' J@B.TEST '})
        assert invited.status_code == 201 and invited.json() == {'user_id': invited.json()['user_id'], 'name':'지수', 'added': True}
        assert owner.post(path, json={'email':'j@b.test'}).json()['added'] is False
        assert owner.post(path, json={'email':'nobody@b.test'}).status_code == 404
        assert stranger.post(path, json={'email':'s@b.test'}).status_code == 403
        assert [r['title'] for r in friend.get('/api/rooms').json()['rooms']] == ['민수의 여행방']
        snapshot = friend.get('/api/rooms/' + room['room_id']).json()
        assert [m['name'] for m in snapshot['members']] == ['민수', '지수'] and snapshot['versions']['participant_version'] == 2
        updated = owner.patch('/api/rooms/' + room['room_id'] + '/trip', json={'start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':200000})
        assert updated.status_code == 200 and updated.json()['config']['per_person_budget_krw'] == 200000
        assert owner.patch('/api/rooms/' + room['room_id'] + '/trip', json={'per_person_budget_krw':-1}).status_code == 422


def test_only_room_owner_can_delete_and_members_are_notified():
    with TestClient(create_app(database_path=':memory:')) as owner, TestClient(owner.app) as friend:
        owner.post('/api/auth/register', json={'name':'민수','email':'m@b.test','password':'password123'})
        friend.post('/api/auth/register', json={'name':'지수','email':'j@b.test','password':'password123'})
        room = owner.post('/api/rooms', json={}).json()
        owner_id = room['members'][0]['user_id']
        assert room['owner_id'] == owner_id
        friend.post('/api/rooms/join', json={'invite_code': room['invite_code']})
        summaries = {client: client.get('/api/rooms').json()['rooms'][0] for client in (owner, friend)}
        assert summaries[owner]['is_owner'] is True and summaries[friend]['is_owner'] is False
        assert summaries[friend]['owner_id'] == owner_id
        assert friend.get('/api/rooms/' + room['room_id']).json()['owner_id'] == owner_id
        assert friend.delete('/api/rooms/' + room['room_id']).status_code == 403
        events_before = owner.app.state.db.get('events:' + room['room_id'])
        assert owner.delete('/api/rooms/' + room['room_id']).json() == {'ok': True}
        assert owner.app.state.db.get('events:' + room['room_id'])[-1]['event'] == 'room.deleted'
        assert len(owner.app.state.db.get('events:' + room['room_id'])) == 1
        assert owner.app.state.db.get('events:' + room['room_id'])[0]['data']['seq'] == events_before[-1]['data']['seq'] + 1
        assert friend.get('/api/rooms/' + room['room_id']).status_code == 404
        assert owner.get('/api/rooms').json()['rooms'] == [] and friend.get('/api/rooms').json()['rooms'] == []
        assert friend.post('/api/rooms/join', json={'invite_code': room['invite_code']}).status_code == 404
        assert owner.delete('/api/rooms/' + room['room_id']).status_code == 404


def test_legacy_room_without_owner_falls_back_to_first_member():
    from backend.services.rooms import room_owner_id
    assert room_owner_id({'members':[{'user_id':'a','name':'A'},{'user_id':'b','name':'B'}]}) == 'a'
    assert room_owner_id({'owner_id':'b','members':[{'user_id':'a','name':'A'}]}) == 'b'


def test_room_title_can_be_renamed_without_replanning():
    with TestClient(create_app(database_path=':memory:')) as owner:
        owner.post('/api/auth/register', json={'name':'민수','email':'m@b.test','password':'password123'})
        room = owner.post('/api/rooms', json={'start_date':'2026-11-21','end_date':'2026-11-22','per_person_budget_krw':1000}).json()
        path = '/api/rooms/' + room['room_id'] + '/trip'
        renamed = owner.patch(path, json={'title':'  부산 바다 여행 '})
        assert renamed.status_code == 200
        assert renamed.json()['title'] == '부산 바다 여행'
        assert renamed.json()['versions']['constraint_version'] == room['versions']['constraint_version']
        assert owner.get('/api/rooms').json()['rooms'][0]['title'] == '부산 바다 여행'
        events = owner.app.state.db.get('events:' + room['room_id'])
        assert events[-1]['data']['changed'] == ['title']
        assert owner.patch(path, json={'title':'   '}).status_code == 422
        assert owner.patch(path, json={'title':'x' * 201}).status_code == 422
        renamed = owner.patch(path, json={'title':'빈 조건 방', 'start_date':'', 'per_person_budget_krw':''})
        assert renamed.status_code == 200, renamed.text
        assert renamed.json()['title'] == '빈 조건 방'
        both = owner.patch(path, json={'title':'여수', 'per_person_budget_krw':2000}).json()
        assert both['title'] == '여수' and both['config']['per_person_budget_krw'] == 2000


def test_only_room_owner_can_rename_but_members_can_edit_trip():
    with TestClient(create_app(database_path=':memory:')) as owner, TestClient(owner.app) as friend:
        owner.post('/api/auth/register', json={'name':'민수','email':'m@b.test','password':'password123'})
        friend.post('/api/auth/register', json={'name':'지수','email':'j@b.test','password':'password123'})
        room = owner.post('/api/rooms', json={}).json()
        friend.post('/api/rooms/join', json={'invite_code': room['invite_code']})
        path = '/api/rooms/' + room['room_id'] + '/trip'
        refused = friend.patch(path, json={'title':'지수의 방'})
        assert refused.status_code == 403
        assert refused.json()['detail'] == 'Only the room owner may rename'
        assert owner.get('/api/rooms/' + room['room_id']).json()['title'] == room['title']
        same_title = friend.patch(path, json={'title':room['title'], 'per_person_budget_krw':5000})
        assert same_title.status_code == 200 and same_title.json()['config']['per_person_budget_krw'] == 5000
        assert owner.patch(path, json={'title':'민수의 제주 여행'}).json()['title'] == '민수의 제주 여행'


def test_new_room_leaves_city_for_the_owner_to_choose():
    with TestClient(create_app(database_path=':memory:')) as owner:
        owner.post('/api/auth/register', json={'name':'민수','email':'m@b.test','password':'password123'})
        assert owner.post('/api/rooms', json={}).json()['config']['region'] == ''
        assert owner.post('/api/rooms', json={'region':'제주'}).json()['config']['region'] == '제주'
