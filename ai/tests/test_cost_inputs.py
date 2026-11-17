from ai.tests.test_place_route_tools import task


def test_cost_inputs_restore_actual_menu_price_and_explicit_basis():
    from ai.cost_inputs import build_cost_inputs
    arguments, questions = build_cost_inputs(task())
    meal = next(l for l in arguments["lines"] if l["evidence_id"] == "fixture:price-a")
    assert meal["unit_price_krw"] == 10000 and meal["scope"] == "per_person"
    assert arguments["budget_by_user"] == {"u1": 200000, "u2": 200000, "u3": 200000, "u4": 200000}
    assert any(l["unit_price_krw"] is None for l in arguments["lines"])


def test_unpriced_shared_menu_requires_input():
    from ai.cost_inputs import build_cost_inputs
    value = task()
    value["observations"][0]["result"]["menus"][0]["serving_basis"] = "한상"
    arguments, questions = build_cost_inputs(value)
    meal = next(l for l in arguments["lines"] if l["category"] == "meal")
    assert meal["unit_price_krw"] is None
    assert any(q["field"] == "menu_selection" and q["target_ref"] == "item-a" for q in questions)


def test_confirmed_personal_budget_overrides_default_only_for_owner():
    from ai.cost_inputs import build_cost_inputs
    value = task()
    value["constraints"] = [dict(owner_id="u1", key="budget_krw", value=150000, kind="hard", status="confirmed"),
                            dict(owner_id="u2", key="budget_krw", value=999, kind="hard", status="needs_owner_confirmation")]
    args, _ = build_cost_inputs(value)
    assert args["budget_by_user"]["u1"] == 150000 and args["budget_by_user"]["u2"] == 200000
