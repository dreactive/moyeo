def test_password_hash_is_salted():
    from backend.auth import hash_password, verify_password
    first = hash_password('correct horse')
    assert first != hash_password('correct horse')
    assert verify_password('correct horse', first)
    assert not verify_password('wrong', first)
