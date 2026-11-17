from backend.db import Database


def test_database_roundtrip(tmp_path):
    path = tmp_path / 'state.sqlite3'
    db = Database(path)
    db.put('room:r', {'members': ['a']})
    db.close()
    second = Database(path)
    assert second.get('room:r') == {'members': ['a']}
    assert second.get('missing') is None
    second.close()
