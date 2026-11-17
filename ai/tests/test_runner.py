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


async def test_observation_changes_next_selected_action():
    from ai.runner import choose_action
    from ai.models.fake_actions import tool
    class Model:
        def generate_json(self, request):
            ref = request["context"]["observations"][0]["result"]["places"][0]["id"]
            return {"candidates": [tool("get_place_details", {"place_ref": ref})]}
        def score_candidates(self, context, candidates):
            return [1.]
    value = task()
    value["observations"] = [{"result": {"places": [{"id": "new-a", "name": "A"}]}, "source_refs": []}]
    first = await choose_action(value, Model(), None, 1)
    value["observations"][0]["result"]["places"][0]["id"] = "new-b"
    second = await choose_action(value, Model(), None, 2)
    assert first["arguments"]["place_ref"] == "new-a"
    assert second["arguments"]["place_ref"] == "new-b"
