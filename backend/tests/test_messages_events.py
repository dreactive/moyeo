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
