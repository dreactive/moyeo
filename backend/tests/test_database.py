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


def test_app_opens_sqlite_in_lifespan(tmp_path):
    from fastapi.testclient import TestClient
    from backend.app import create_app
    with TestClient(create_app(database_path=tmp_path / 'test.db')) as client:
        client.app.state.db.put('probe', {'ok': True})
        assert client.app.state.db.get('probe') == {'ok': True}


def test_multi_record_write_does_not_partially_commit():
    import pytest
    from backend.db import Database
    db = Database(':memory:')
    db.put('a', 1)
    with pytest.raises(TypeError):
        db.put_many({'a':2, 'b':object()})
    assert db.get('a') == 1
