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


async def test_empty_room_first_mention_creates_initial_plan():
    from ai.runtime import create_runtime
    value = task()
    value.update(items=[], current_plan=None, observations=[], questions=[])
    value["recent_messages"] = [dict(value["recent_messages"][0], id="new", text="가상 A식당 가자")]
    value["goal"] = "message_created"
    value["config"]["day_start_time"] = "10:00"
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    result = await runtime.run(value, None)
    await runtime.aclose()
    assert result["plan_draft"]["selected_item_ids"] == ["client:new"]
    assert {"search_places", "get_place_details", "get_car_route", "build_itinerary", "calculate_costs"} <= {
        o["tool_name"] for o in result["observations"]}
    assert result["item_proposals"][0]["client_ref"] == "client:new"


async def test_first_plan_reaches_ready_after_explicit_menu_and_car_inputs():
    from copy import deepcopy
    from ai.runtime import create_runtime
    value = task()
    template = deepcopy(value["current_plan"])
    value.update(items=[], current_plan=None, observations=[], questions=[], goal="message_created")
    value["recent_messages"] = [dict(value["recent_messages"][0], id="new", text="가상 A식당 가자")]
    value["config"]["day_start_time"] = "10:00"
    value["config"]["fixed_costs"].append(dict(value["config"]["fixed_costs"][0],
        id="car-input", category="car", description="유류·주차 포함 차량비", unit_price_krw=10000, paid=False))
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    first = await runtime.run(value, None)
    assert first["completion"] == "needs_input"
    visit = first["plan_draft"]["days"][0]["visits"][0]
    value.update(goal="question_answered", recent_messages=[], observations=first["observations"],
        items=[dict(id="client:new", item_version=1, kind="place", title="가상 A식당", source_message_ids=["new"])])
    value["current_plan"] = dict(template, **first["plan_draft"], item_snapshots=[
        dict(id="client:new", place_ref=visit["place_ref"], title="가상 A식당")])
    value["questions"] = [dict(q, status="answered", answered_by="u1",
        answer={"menu_id": "fixture:menu-a", "quantity": 1, "scope": "per_person"})
        for q in first["questions"] if q["field"] == "menu_selection"]
    second = await runtime.run(value, None)
    await runtime.aclose()
    assert second["completion"] == "done" and second["plan_draft"]["validation"] == "ready"
    assert second["plan_draft"]["cost"]["total_krw"] == 130000
    assert not second["questions"] and not second["conflicts"]
