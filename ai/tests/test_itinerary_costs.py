def test_shared_remainder_and_per_person_without_owner():
    from ai.tools.costs import allocate
    assert allocate({"scope": "shared", "unit_price_krw": 101, "quantity": 1}, ["u4", "u2", "u1", "u3"]) == {
        "u1": 26, "u2": 25, "u3": 25, "u4": 25}
    assert allocate({"scope": "per_person", "unit_price_krw": 10000, "quantity": 1}, ["u1", "u2"]) == {
        "u1": 10000, "u2": 10000}


def test_budget_paid_and_projected_balances():
    from ai.tools.costs import calculate_costs
    lines = [{"id": "paid", "scope": "per_person", "unit_price_krw": 80000, "quantity": 1, "paid": True},
             {"id": "future", "scope": "per_person", "unit_price_krw": 70000, "quantity": 1, "paid": False}]
    result = calculate_costs(lines, ["u1"], {"u1": 200000})
    assert result["total_krw"] == 150000
    assert result["remaining_budget_krw"] == {"u1": 120000}
    assert result["planned_balance_krw"] == {"u1": 50000}
