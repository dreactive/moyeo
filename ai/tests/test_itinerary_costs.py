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


def test_itinerary_schedules_observed_inbound_leg():
    from ai.tools.itinerary import build_itinerary
    config = {"start_date": "2026-11-21", "end_date": "2026-11-21"}
    visit = {"item_id": "a", "place_ref": "p", "date": "2026-11-21", "stay_minutes": 60}
    leg = {"from_ref": "anchor:origin", "to_ref": "p", "duration_seconds": 180}
    result = build_itinerary([visit], {"origin": {}, "destination": {}}, [], [leg], config)
    assert result["days"][0]["visits"][0]["start_at"] == "2026-11-21T09:03:00+09:00"
    assert result["days"][0]["route_legs"] == [leg]


def test_return_deadline_includes_outbound_leg():
    from ai.tools.itinerary import finish_day
    day = {"date": "2026-11-21", "visits": [{"item_id": "a", "place_ref": "p",
            "end_at": "2026-11-21T15:30:00+09:00"}], "route_legs": []}
    leg = {"from_ref": "p", "to_ref": "anchor:destination", "duration_seconds": 3600}
    conflicts, questions = finish_day(day, "anchor:destination", [leg], "16:00", {})
    assert conflicts[0]["type"] == "time"
    assert conflicts[0]["blocking"] is True
    assert day["route_legs"] == [leg]
    assert not questions


def test_holiday_and_unknown_hours_are_distinct():
    from ai.tools.hours import validate_hours
    visit = {"item_id": "a", "date": "2026-11-21", "start_at": "2026-11-21T11:00:00+09:00",
             "end_at": "2026-11-21T12:00:00+09:00"}
    closed = {"opening_hours": {"intervals": [], "holiday_text": "2026-11-21 휴무"}}
    conflicts, questions = validate_hours(visit, closed, {})
    assert conflicts[0]["type"] == "opening_hours" and not questions
    conflicts, questions = validate_hours(visit, {"opening_hours": None}, {})
    assert not conflicts and questions[0]["target_ref"] == "a"


def test_confirmed_personal_return_limit_is_enforced_by_builder():
    from ai.tools.itinerary import build_itinerary
    config = {"start_date": "2026-11-21", "end_date": "2026-11-21"}
    visit = {"item_id": "a", "place_ref": "p", "date": "2026-11-21",
             "preferred_start_at": "2026-11-21T15:00:00+09:00", "stay_minutes": 60}
    legs = [{"from_ref": "anchor:origin", "to_ref": "p", "duration_seconds": 0},
            {"from_ref": "p", "to_ref": "anchor:destination", "duration_seconds": 1800}]
    constraints = [{"key": "return_by", "value": "16:00", "kind": "hard", "status": "confirmed"}]
    result = build_itinerary([visit], {"origin": {}, "destination": {}}, constraints, legs, config)
    assert any(c["type"] == "time" for c in result["conflicts"])


def test_builder_applies_observed_holiday_and_reports_missing_anchors():
    from ai.tools.itinerary import build_itinerary
    config = {"start_date": "2026-11-21", "end_date": "2026-11-21",
              "_details": {"p": {"opening_hours": {"intervals": [], "holiday_text": "2026-11-21 휴무"}}}}
    visit = {"item_id": "a", "place_ref": "p", "date": "2026-11-21", "stay_minutes": 60}
    leg = {"from_ref": "anchor:origin", "to_ref": "p", "duration_seconds": 60}
    result = build_itinerary([visit], {"origin": None, "destination": None}, [], [leg], config)
    assert any(c["type"] == "opening_hours" for c in result["conflicts"])
    assert any(q["field"] == "origin" for q in result["questions"])


def test_empty_last_day_keeps_lodging_to_destination_route():
    from ai.tools.itinerary import build_itinerary
    leg = {"from_ref": "anchor:lodging", "to_ref": "anchor:destination", "duration_seconds": 600}
    result = build_itinerary([], {"origin": {}, "lodging": {}, "destination": {}}, [], [leg],
                             {"start_date": "2026-11-21", "end_date": "2026-11-22"})
    assert result["days"][1]["route_legs"] == [leg]


def test_same_pair_on_two_days_consumes_the_correct_ordered_leg():
    from ai.tools.itinerary import build_itinerary
    visits = [dict(item_id=p + day, place_ref=p, date=day, stay_minutes=60) for day in ("2026-11-21", "2026-11-22") for p in ("a", "b")]
    def leg(a, b, seconds, evidence):
        return dict(from_ref=a, to_ref=b, duration_seconds=seconds, evidence_id=evidence)
    legs = [leg("anchor:origin", "a", 600, "in1"), leg("a", "b", 600, "ab1"), leg("b", "anchor:lodging", 600, "out1"),
            leg("anchor:lodging", "a", 600, "in2"), leg("a", "b", 3600, "ab2"), leg("b", "anchor:destination", 600, "out2")]
    result = build_itinerary(visits, {}, [], legs, {"start_date": "2026-11-21", "end_date": "2026-11-22"})
    assert result["days"][1]["visits"][1]["start_at"] == "2026-11-22T11:10:00+09:00"
    assert result["days"][1]["route_legs"][1]["evidence_id"] == "ab2"
def test_fractional_quantity_keeps_exact_krw_and_rejects_subwon_truncation():
    import pytest
    from ai.tools.costs import allocate
    line = dict(scope="shared", unit_price_krw=10000, quantity=.5)
    assert allocate(line, ["u1"]) == {"u1": 5000}
    with pytest.raises(ValueError):
        allocate(dict(line, unit_price_krw=10001), ["u1"])
