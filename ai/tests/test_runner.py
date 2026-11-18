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
            return [1.] + [0.] * (len(candidates) - 1)
    value = task()
    value["observations"] = [{"tool_name": "search_places", "arguments": {}, "observed_at": "2026-11-18T00:00:00+09:00",
                              "result": {"places": [{"id": "new-a", "name": "A"}]}, "source_refs": []}]
    first = await choose_action(value, Model(), None, 1)
    value["observations"][0]["result"]["places"][0]["id"] = "new-b"
    second = await choose_action(value, Model(), None, 2)
    assert first["arguments"]["place_ref"] == "new-a"
    assert second["arguments"]["place_ref"] == "new-b"


async def test_candidate_generation_does_not_execute_or_fake_completion():
    from ai.runner import run_steps
    from ai.result import empty_result
    from ai.models.fake_actions import tool
    class Model:
        def generate_json(self, request):
            query = "A" + str(len(request["context"]["observations"]))
            return {"candidates": [tool("search_places", {"query": query, "region": "여수", "category": None})]}
        def score_candidates(self, context, candidates):
            return [1.] + [0.] * (len(candidates) - 1)
    class Tools:
        calls = 0
        async def execute(self, name, arguments):
            self.calls += 1
            return {"places": []}
    value, tools = task(), Tools()
    result = empty_result(value)
    await run_steps(value, Model(), tools, None, result)
    assert tools.calls == 0 and result["observations"] == []
    assert result["candidates"][0]["tool_name"] == "search_places"
    assert result["completion"] == "needs_input" and not result["questions"]


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


async def test_invalid_model_scores_return_needs_input_without_tool_call():
    from ai.runner import run_agent
    from ai.models.fake_actions import tool
    class Model:
        def generate_json(self, request):
            return {} if request["phase"] == "extract" else {"candidates": [tool("search_places",
                {"query": "A", "region": "여수", "category": None})]}
        def score_candidates(self, context, candidates):
            return [float("nan")]
    class Tools:
        async def execute(self, name, arguments):
            raise AssertionError("Invalid decision executed")
    result = await run_agent(task(), Model(), Tools(), None)
    assert result["completion"] == "needs_input"
    assert all(q["field"] != "constraint_value" or q["target_ref"] for q in result["questions"])
    assert not result["observations"]


async def test_rule_assistance_is_labeled_and_does_not_skip_base_generation():
    from ai.runner import run_agent
    class Model:
        mode = "local_qwen"
        calls = 0
        def generate_json(self, request):
            self.calls += 1
            return {}
    model, events, value = Model(), [], task()
    value["goal"] = "chat"
    async def sink(event):
        events.append(event)
    result = await run_agent(value, model, None, sink)
    assert model.calls == 1 and result["constraint_proposals"][0]["value"] == 200000
    assert events[0]["payload"]["extraction_mode"] == "rule-assisted"
    assert events[0]["payload"]["model_mode"] == "local_qwen"


async def test_ready_unchanged_plan_still_generates_candidates():
    from ai.runner import run_steps
    from ai.result import empty_result
    from ai.models.fake import FakeModelBackend
    value = task()
    value["recent_messages"] = []
    value["current_plan"]["validation"] = "ready"
    value["questions"] = []
    value["current_plan"].update(value["base_versions"])
    result = empty_result(value)
    await run_steps(value, FakeModelBackend(), None, None, result)
    assert result["completion"] == "needs_input" and result["candidates"]
    assert result["plan_draft"] is None


async def test_action_model_receives_code_derived_calculations_and_route_time():
    from ai.runner import choose_action
    class Model:
        def generate_json(self, request):
            context = request["context"]
            assert context["needed_route"]["departure_at"] == "2026-11-21T09:00:00+09:00"
            meal = next(l for l in context["available_calculations"]["calculate_costs"]["lines"] if l["category"] == "meal")
            assert meal["unit_price_krw"] == 10000
            return {"candidates": [dict(action="ask", reason="test", tool_name=None, arguments={}, source_message_ids=[], source_refs=[])]}
        def score_candidates(self, context, candidates):
            return [1.] + [0.] * (len(candidates) - 1)
    assert (await choose_action(task(), Model(), None, 1))["action"] == "ask"


async def test_judge_can_select_later_day_instead_of_first_pipeline_step():
    from ai.runner import choose_action
    class Model:
        def generate_json(self, request):
            return {"candidates": []}
        def score_candidates(self, context, candidates):
            return [10. if c["arguments"].get("from_ref") == "anchor:lodging" else 0. for c in candidates]
    action = await choose_action(task(), Model(), None, 1)
    assert action["tool_name"] == "get_car_route" and action["arguments"]["from_ref"] == "anchor:lodging"


def test_budget_overrun_is_blocking_even_when_calculation_is_complete():
    from ai.outcome import assemble_result
    from ai.result import empty_result
    from ai.tools.costs import calculate_costs
    value = task()
    result = empty_result(value)
    cost = calculate_costs([dict(scope="per_person", unit_price_krw=20000, quantity=1, paid=False)], ["u1"], {"u1": 10000})
    result["observations"] = [
        dict(tool_name="build_itinerary", result=dict(days=value["current_plan"]["days"], questions=[], conflicts=[])),
        dict(tool_name="calculate_costs", result=cost)]
    assemble_result(value, result)
    assert result["completion"] == "needs_input" and result["plan_draft"]["validation"] == "conflict"
    assert any(c["type"] == "budget" and c["blocking"] and c["options"] for c in result["conflicts"])


async def test_manual_replan_does_not_reuse_old_ready_plan():
    from ai.runtime import create_runtime
    value = task()
    value.update(goal="manual_replan", questions=[], recent_messages=[])
    value["current_plan"].update(value["base_versions"], validation="ready")
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    result = await runtime.run(value, None)
    await runtime.aclose()
    assert result["candidates"] and result["observations"] == []
    assert result["plan_draft"] is None


def test_unverified_minority_hard_condition_requires_its_owner_without_relaxing():
    from ai.outcome import assemble_result
    from ai.result import empty_result
    value = task()
    value["constraints"] = [dict(id="diet", owner_id="u4", key="avoid_spicy", value=True, kind="hard", status="confirmed")]
    result = empty_result(value)
    result["observations"] = [dict(tool_name="build_itinerary", result=dict(days=value["current_plan"]["days"], questions=[], conflicts=[])),
        dict(tool_name="calculate_costs", result=dict(total_krw=120000, planned_balance_krw={"u1": 170000}))]
    assemble_result(value, result)
    assert any(q["field"] == "constraint_value" and q["target_ref"] == "diet" and q["owner_id"] == "u4" for q in result["questions"])
    assert value["constraints"][0]["value"] is True and result["completion"] == "needs_input"
