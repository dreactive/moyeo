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


def test_unselected_visit_cost_is_unknown_instead_of_silently_free():
    from ai.cost_inputs import build_cost_inputs
    value = task()
    value["current_plan"]["days"][0]["visits"][0]["selected_menu_ids"] = []
    args, questions = build_cost_inputs(value)
    assert any(q["field"] == "menu_selection" and q["target_ref"] == "item-a" for q in questions)
    assert any(l["unit_price_krw"] is None and "item-a" in l["id"] for l in args["lines"])


def test_explicit_car_extras_resolve_unknown_and_observed_tolls_are_counted_once():
    from ai.cost_inputs import build_cost_inputs
    value = task()
    value["config"]["fixed_costs"].append(dict(value["config"]["fixed_costs"][0], id="car-input", category="car",
        description="도시 내 유류·주차 포함 차량비", unit_price_krw=10000, quantity=1, paid=False))
    route = dict(tool_name="get_car_route", arguments=dict(from_ref="anchor:origin", to_ref="fixture:place-a",
        departure_at="2026-11-21T09:00:00+09:00"), result=dict(from_ref="anchor:origin", to_ref="fixture:place-a",
        duration_seconds=600, toll_krw=3000, evidence_id="fixture:toll"))
    value["observations"] += [route, route]
    args, _ = build_cost_inputs(value)
    assert not any(l["id"] == "car:extras" for l in args["lines"])
    assert [l["unit_price_krw"] for l in args["lines"] if l["evidence_id"] == "fixture:toll"] == [3000]


def test_tolls_are_still_unknown_if_car_price_explicitly_excludes_them():
    from ai.cost_inputs import build_cost_inputs
    value = task()
    value["config"]["fixed_costs"].append(dict(value["config"]["fixed_costs"][0], id="car-input", category="car",
        description="통행료 별도 유류·주차 포함 차량비", unit_price_krw=10000, quantity=1, paid=False))
    args, _ = build_cost_inputs(value)
    assert any(line["id"].startswith("toll:unobserved:") for line in args["lines"])


def test_canonical_cost_arguments_reject_numeric_boolean_substitution():
    import pytest
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.registry import RegisteredTools
    from ai.tools.validation import validate_arguments
    value = task()
    value["config"]["fixed_costs"][0]["unit_price_krw"] = 1
    args, _ = build_cost_inputs(value)
    args["lines"][0]["unit_price_krw"] = True
    with pytest.raises(ValueError, match="differ from observed"):
        validate_arguments("calculate_costs", args, RegisteredTools(value).context)
