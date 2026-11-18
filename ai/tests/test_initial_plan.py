from ai.tests.test_place_route_tools import task


def test_initial_visits_resolve_unique_observed_place_without_existing_plan():
    from ai.planning import planned_visits
    value = task()
    value["current_plan"] = None
    value["items"] = [dict(id="client:new", kind="place", title="가상 A식당", item_version=1)]
    place = value["observations"][0]["result"]["place"]
    value["observations"] = [dict(tool_name="search_places",
        arguments={"query": "가상 A식당", "region": "여수", "category": None},
        result={"places": [place]}, observed_at="now", source_refs=[])]
    visits = planned_visits(value)
    assert visits[0]["item_id"] == "client:new" and visits[0]["place_ref"] == "fixture:place-a"
    value["observations"][0]["result"]["places"].append(dict(place, id="other:branch"))
    assert planned_visits(value) == []


async def test_initial_fixture_search_and_details_need_no_prior_room_observations():
    from ai.tools.registry import RegisteredTools
    value = task()
    value["observations"] = []
    tools = RegisteredTools(value)
    places = await tools.execute("search_places", {"query": "가상 A식당", "region": "여수", "category": None})
    assert places["places"][0]["id"] == "fixture:place-a"
    tools.remember(dict(tool_name="search_places", arguments={}, result=places, observed_at="now", source_refs=[]))
    detail = await tools.execute("get_place_details", {"place_ref": "fixture:place-a"})
    assert detail["menus"][0]["price_krw"] == 10000


async def test_empty_room_first_mention_executes_search_and_dependent_calls():
    from ai.runtime import create_runtime
    value = task()
    value.update(items=[], current_plan=None, observations=[], questions=[], goal="message_created")
    value["recent_messages"] = [dict(value["recent_messages"][0], id="new", text="A식당 가자")]
    value["config"]["day_start_time"] = "10:00"
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    try:
        result = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    assert [o["tool_name"] for o in result["observations"]] == [
        "search_places", "get_place_details", "get_car_route", "get_car_route", "get_car_route", "build_itinerary"]
    assert result["observations"][0]["arguments"] == dict(query="A식당", region="여수", category=None)
    assert result["observations"][1]["arguments"] == {"place_ref": "fixture:place-a"}
    assert result["observations"][2]["arguments"]["departure_at"] == "2026-11-21T10:00:00+09:00"
    assert result["item_proposals"][0]["source_message_ids"] == ["new"]
    assert result["item_proposals"][0]["title"] == "A식당"
    assert result["completion"] == "needs_input" and result["plan_draft"] is None
    assert result["decision_report"]["reason"] == "round_limit"


async def test_repeated_runs_preserve_input_and_repeat_only_the_unapplied_selected_work():
    from copy import deepcopy
    from ai.runtime import create_runtime
    value = task()
    value.update(items=[], current_plan=None, observations=[], questions=[], goal="message_created")
    value["recent_messages"] = [dict(value["recent_messages"][0], id="new", text="A식당 가자")]
    value["config"]["day_start_time"] = "10:00"
    before = deepcopy(value)
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture", "max_decision_rounds": 1})
    try:
        first = await runtime.run(value, None)
        second = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    assert value == before
    assert first["candidates"] == second["candidates"]
    assert first["item_proposals"] == second["item_proposals"]
    assert len(first["observations"]) == len(second["observations"]) == 1
    assert first["observations"][0]["arguments"] == second["observations"][0]["arguments"] == dict(
        query="A식당", region="여수", category=None)
    assert first["observations"][0]["tool_name"] == second["observations"][0]["tool_name"] == "search_places"
    assert first["completion"] == second["completion"] == "needs_input"
    assert first["plan_draft"] is second["plan_draft"] is None
