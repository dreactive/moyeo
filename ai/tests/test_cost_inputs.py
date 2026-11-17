from ai.tests.test_place_route_tools import task


def test_cost_inputs_restore_actual_menu_price_and_explicit_basis():
    from ai.cost_inputs import build_cost_inputs
    arguments, questions = build_cost_inputs(task())
    meal = next(l for l in arguments["lines"] if l["evidence_id"] == "fixture:price-a")
    assert meal["unit_price_krw"] == 10000 and meal["scope"] == "per_person"
    assert arguments["budget_by_user"] == {"u1": 200000, "u2": 200000, "u3": 200000, "u4": 200000}
    assert any(l["unit_price_krw"] is None for l in arguments["lines"])
