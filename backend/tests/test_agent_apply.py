def test_sources_are_room_scoped_and_owned(room):
    from backend.domain import valid_sources
    assert valid_sources(room, ['m4'], 'u4')
    assert not valid_sources(room, ['m4'], 'u1')
    assert not valid_sources(room, ['missing'])
    assert not valid_sources(room, [])
