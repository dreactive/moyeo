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


async def test_twenty_action_limit_does_not_fake_completion():
    from ai.runner import run_steps
    from ai.result import empty_result
    from ai.models.fake_actions import tool
    class Model:
        def generate_json(self, request):
            return {"candidates": [tool("search_places", {"query": "A", "region": "여수", "category": None})]}
        def score_candidates(self, context, candidates):
            return [1.]
    class Tools:
        calls = 0
        async def execute(self, name, arguments):
            self.calls += 1
            return {"places": []}
    value, tools = task(), Tools()
    result = empty_result(value)
    await run_steps(value, Model(), tools, None, result)
    assert tools.calls == 20 and len(result["observations"]) == 20
    assert result["completion"] == "needs_input" and result["questions"]


def test_plan_result_uses_only_executed_calculations_and_retains_null():
    from ai.outcome import assemble_result
    from ai.result import empty_result
    value = task()
    result = empty_result(value)
    result["observations"] = [
        dict(tool_name="build_itinerary", result={"days": value["current_plan"]["days"], "conflicts": [], "questions": []}),
        dict(tool_name="calculate_costs", result={"total_krw": None, "planned_balance_krw": {"u1": None}})]
    assert assemble_result(value, result)
    assert result["completion"] == "needs_input"
    assert set(result["plan_draft"]) == {"selected_item_ids", "days", "cost", "validation", "blocking_conflict_ids"}
