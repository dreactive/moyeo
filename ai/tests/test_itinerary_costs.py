def test_shared_remainder_and_per_person_without_owner():
    from ai.tools.costs import allocate
    assert allocate({"scope": "shared", "unit_price_krw": 101, "quantity": 1}, ["u4", "u2", "u1", "u3"]) == {
        "u1": 26, "u2": 25, "u3": 25, "u4": 25}
    assert allocate({"scope": "per_person", "unit_price_krw": 10000, "quantity": 1}, ["u1", "u2"]) == {
        "u1": 10000, "u2": 10000}
