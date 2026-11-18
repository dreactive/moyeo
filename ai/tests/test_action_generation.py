from ai.tests.test_place_route_tools import task


def test_observation_changes_fixture_next_action():
    from ai.models.fake_actions import propose_actions
    value = task()
    value["observations"] = []
    action = propose_actions(value)[0]
    assert action["tool_name"] == "get_place_details"
    value["observations"] = task()["observations"]
    assert propose_actions(value)[0]["tool_name"] == "get_car_route"
    changed = task()
    changed["current_plan"]["item_snapshots"][0]["place_ref"] = "fixture:other"
    changed["observations"] = []
    assert propose_actions(changed)[0]["arguments"]["place_ref"] == "fixture:other"


def test_next_route_uses_prior_duration_and_visit_departure_time():
    from ai.planning import next_route
    value = task()
    first = next_route(value)
    assert first["departure_at"] == "2026-11-21T09:00:00+09:00"
    value["observations"].append(dict(tool_name="get_car_route", arguments=first,
        result=dict(from_ref=first["from_ref"], to_ref=first["to_ref"], duration_seconds=180)))
    following = next_route(value)
    assert following["from_ref"] == "fixture:place-a"
    assert following["to_ref"] == "fixture:place-b"
    assert following["departure_at"] == "2026-11-21T12:30:00+09:00"


def test_independent_day_routes_are_real_alternatives():
    from ai.planning import pending_routes
    value = task()
    routes = pending_routes(value)
    assert [(r["from_ref"], r["to_ref"]) for r in routes] == [
        ("anchor:origin", "fixture:place-a"), ("anchor:lodging", "anchor:destination")]
    value["observations"].append(dict(tool_name="get_car_route", arguments=routes[0],
        result=dict(from_ref=routes[0]["from_ref"], to_ref=routes[0]["to_ref"], duration_seconds=180)))
    assert pending_routes(value)[0]["from_ref"] == "fixture:place-a"
