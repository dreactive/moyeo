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


def test_unknown_unpaid_cost_does_not_erase_known_paid_balance():
    from ai.tools.costs import calculate_costs
    lines = [{"scope": "shared", "unit_price_krw": 80000, "quantity": 1, "paid": True},
             {"scope": "shared", "unit_price_krw": None, "quantity": 1, "paid": False}]
    result = calculate_costs(lines, ["u1", "u2"], {"u1": 200000, "u2": 200000})
    assert result["total_krw"] is None
    assert result["known_total_krw"] == 80000
    assert result["remaining_budget_krw"] == {"u1": 160000, "u2": 160000}
    assert result["planned_balance_krw"] == {"u1": None, "u2": None}
    assert result["unknown_line_count"] == 1


def test_visit_time_uses_route_seconds_and_explicit_stay_assumption():
    from datetime import datetime
    from ai.tools.itinerary import schedule_visit
    visit = {"item_id": "a", "place_ref": "p", "date": "2026-11-21",
             "preferred_start_at": None, "stay_minutes": None, "selected_menu_ids": []}
    scheduled = schedule_visit(visit, datetime.fromisoformat("2026-11-21T09:00:00+09:00"), 180)
    assert scheduled["start_at"] == "2026-11-21T09:03:00+09:00"
    assert scheduled["end_at"] == "2026-11-21T10:03:00+09:00"
    assert scheduled["assumptions"]


def test_itinerary_missing_route_requires_input():
    from ai.tools.itinerary import build_itinerary
    config = {"start_date": "2026-11-21", "end_date": "2026-11-22"}
    anchors = {x: {"latitude": 34.7, "longitude": 127.6} for x in ("origin", "lodging", "destination")}
    visit = {"item_id": "a", "place_ref": "p", "date": "2026-11-21", "stay_minutes": 60}
    result = build_itinerary([visit], anchors, [], [], config)
    assert [d["date"] for d in result["days"]] == ["2026-11-21", "2026-11-22"]
    assert result["questions"]
    assert result["days"][0]["visits"] == []
