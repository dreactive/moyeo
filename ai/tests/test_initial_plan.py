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
