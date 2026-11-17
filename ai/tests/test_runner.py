from ai.tests.test_place_route_tools import task


async def test_observations_survive_disabled_trace():
    from ai.runner import execute_selected
    from ai.tools.registry import RegisteredTools
    value = task()
    action = dict(tool_name="get_place_details", arguments={"place_ref": "fixture:place-a"})
    observation = await execute_selected(value, action, RegisteredTools(value), None, 1)
    assert observation["result"]["menus"][0]["price_krw"] == 10000
    assert observation["tool_name"] == "get_place_details"
    assert "fixture:price-a" in observation["source_refs"]
