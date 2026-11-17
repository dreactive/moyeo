import json
from pathlib import Path
import pytest


def task():
    return json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))


async def test_details_restored_and_cross_room_isolation():
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(task(), "fixture")
    result = await tools.execute("get_place_details", {"place_ref": "fixture:place-a"})
    assert result["menus"][0]["price_krw"] == 10000
    other = task()
    other["observations"] = []
    with pytest.raises(ValueError):
        await RegisteredTools(other, "fixture").execute("get_place_details", {"place_ref": "unknown"})


async def test_route_anchors_units_and_missing_leg():
    from ai.tools.registry import RegisteredTools
    context = task()
    context["observations"].append({"tool_name": "get_car_route", "arguments": {"from_ref": "anchor:origin",
        "to_ref": "fixture:place-a", "departure_at": None}, "result": {
        "from_ref": "anchor:origin", "to_ref": "fixture:place-a", "distance_m": 1200,
        "duration_seconds": 180, "toll_krw": None, "polyline": [], "evidence_id": "fixture:route"}})
    tools = RegisteredTools(context)
    route = await tools.execute("get_car_route", {"from_ref": "anchor:origin",
                                "to_ref": "fixture:place-a", "departure_at": None})
    assert (route["distance_m"], route["duration_seconds"]) == (1200, 180)
    with pytest.raises(ValueError):
        await tools.execute("get_car_route", {"from_ref": "fixture:place-a", "to_ref": "anchor:destination"})


async def test_route_cache_does_not_cross_departure_time():
    from ai.tools.registry import RegisteredTools
    context = task()
    context["observations"] = [{"tool_name": "get_car_route",
        "arguments": {"from_ref": "anchor:origin", "to_ref": "anchor:destination",
                      "departure_at": "2026-11-21T09:00:00+09:00"},
        "result": {"from_ref": "anchor:origin", "to_ref": "anchor:destination",
                   "distance_m": 1000, "duration_seconds": 300, "polyline": []}}]
    with pytest.raises(ValueError):
        from ai.tools.routes import observed_route
        from ai.tools.context import build_tool_context
        observed_route(build_tool_context(context),
            {"from_ref": "anchor:origin", "to_ref": "anchor:destination",
             "departure_at": "2026-11-21T17:00:00+09:00"})


async def test_registry_search_and_calculation_are_server_independent():
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(task())
    result = await tools.execute("search_places", {"query": "A식당", "region": "여수", "category": None})
    assert [p["id"] for p in result["places"]] == ["fixture:place-a"]
    from ai.cost_inputs import build_cost_inputs
    from ai.planning import next_route
    value = task()
    while arguments := next_route(value):
        route = await tools.execute("get_car_route", arguments)
        observation = dict(tool_name="get_car_route", arguments=arguments, result=route)
        value["observations"].append(observation)
        tools.remember(observation)
    summary = await tools.execute("calculate_costs", build_cost_inputs(value)[0])
    assert summary["known_total_krw"] == 120000


async def test_registry_remembers_search_observation_without_global_state():
    from ai.tools.registry import RegisteredTools
    tools = RegisteredTools(task())
    tools.remember({"tool_name": "search_places", "arguments": {}, "result": {"places": [
        {"id": "room:new", "name": "같은이름", "latitude": 35, "longitude": 127, "provider_refs": {"x": "1"}}]}})
    assert "room:new" in tools.context["places"]
    assert "room:new" not in RegisteredTools(task()).context["places"]


async def test_explicit_fixture_routes_are_not_created_for_changed_anchors():
    from ai.providers.fixture import fixture_route
    context = task()
    args = {"from_ref": "anchor:origin", "to_ref": "fixture:place-a", "departure_at": None}
    route = fixture_route(context, args)
    assert route["evidence_id"].startswith("fixture:")
    assert route["duration_seconds"] == 600
    context["config"]["origin"]["latitude"] = 37.5
    with pytest.raises(ValueError):
        fixture_route(context, args)


async def test_itinerary_uses_only_route_observed_for_actual_departure():
    from ai.planning import itinerary_arguments
    from ai.tools.registry import RegisteredTools
    value = task()
    value["current_plan"]["days"][0]["visits"] = value["current_plan"]["days"][0]["visits"][:1]
    value["current_plan"]["selected_item_ids"] = ["item-a"]
    value["current_plan"]["days"][0]["visits"][0]["start_at"] = None
    def observed(a, b, when, seconds, evidence):
        return dict(tool_name="get_car_route", arguments=dict(from_ref=a, to_ref=b, departure_at=when),
            result=dict(from_ref=a, to_ref=b, distance_m=1000, duration_seconds=seconds, toll_krw=0, polyline=[], evidence_id=evidence))
    value["observations"] += [
        observed("anchor:origin", "fixture:place-a", "2026-11-20T09:00:00+09:00", 600, "old"),
        observed("anchor:origin", "fixture:place-a", "2026-11-21T09:00:00+09:00", 3600, "new"),
        observed("fixture:place-a", "anchor:lodging", "2026-11-21T11:00:00+09:00", 600, "to-lodging"),
        observed("anchor:lodging", "anchor:destination", "2026-11-22T09:00:00+09:00", 600, "return")]
    result = await RegisteredTools(value).execute("build_itinerary", itinerary_arguments(value))
    assert result["days"][0]["visits"][0]["start_at"] == "2026-11-21T10:00:00+09:00"
    assert result["days"][0]["route_legs"][0]["evidence_id"] == "new"


def test_changed_anchor_invalidates_same_time_live_route_observation():
    from ai.providers.kakao import route_evidence_id
    from ai.tools.context import build_tool_context
    from ai.planning import next_route
    value = task()
    args = dict(from_ref="anchor:origin", to_ref="fixture:place-a", departure_at="2026-11-21T09:00:00+09:00")
    evidence = route_evidence_id(build_tool_context(value)["places"], args)
    value["observations"].append(dict(tool_name="get_car_route", arguments=args, result=dict(
        from_ref=args["from_ref"], to_ref=args["to_ref"], duration_seconds=600, evidence_id=evidence)))
    assert next_route(value)["from_ref"] == "fixture:place-a"
    value["config"]["origin"]["latitude"] = 35
    assert next_route(value)["from_ref"] == "anchor:origin"
