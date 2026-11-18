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


def test_observation_changes_code_prepared_detail_candidate():
    from ai.decision_candidates import build_decision_candidates
    value = task()
    value.update(current_plan=None, items=[dict(id="item", kind="place", title="A")])
    value["observations"] = [dict(tool_name="search_places", arguments=dict(query="A", region="여수", category=None),
        result={"places": [dict(id="new-a", name="A")]}, source_refs=[])]
    first = build_decision_candidates(value)["candidates"]
    value["observations"][0]["result"]["places"][0]["id"] = "new-b"
    second = build_decision_candidates(value)["candidates"]
    assert first[0]["arguments"] == {"place_ref": "new-a"}
    assert second[0]["arguments"] == {"place_ref": "new-b"}
    assert first[0]["candidate_id"] != second[0]["candidate_id"]


async def test_judge_failure_holds_real_candidates_without_executing_or_claiming_completion(monkeypatch):
    from ai.runtime import create_runtime
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    def fail(context, candidates):
        raise RuntimeError("fixture judge unavailable")
    monkeypatch.setattr(runtime.model.backend, "score_candidates", fail)
    events = []
    async def sink(event):
        events.append(event)
    value = task()
    try:
        result = await runtime.run(value, sink)
    finally:
        await runtime.aclose()
    assert [c["tool_name"] for c in result["candidates"]] == ["get_car_route", "get_car_route"]
    assert result["observations"] == [] and result["plan_draft"] is None
    assert result["questions"] == value["questions"]
    assert result["completion"] == "needs_input" and result["decision_report"]["status"] == "failed"
    assert not any(e["event"] == "tool_call" for e in events)
    failure = events[-1]["payload"]
    assert failure["termination"] == "judge_failed" and failure["selected_index"] is None and failure["scores"] == []


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


async def test_runtime_executes_exact_judge_selected_alternative_and_holds_later_scoring_failure(monkeypatch):
    from copy import deepcopy
    from ai.runtime import create_runtime
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    decisions = []
    def score(context, candidates):
        decisions.append(deepcopy(candidates))
        if len(decisions) > 1:
            raise RuntimeError("second comparison unavailable")
        return [0., 10.]
    monkeypatch.setattr(runtime.model.backend, "score_candidates", score)
    try:
        result = await runtime.run(task(), None)
    finally:
        await runtime.aclose()
    assert len(decisions) == 2 and len(decisions[0]) == 2
    assert len(result["observations"]) == 1
    selected = decisions[0][1]
    assert selected["arguments"] == dict(from_ref="anchor:lodging", to_ref="anchor:destination",
        departure_at="2026-11-22T09:00:00+09:00")
    assert result["observations"][0]["tool_name"] == selected["tool_name"] == "get_car_route"
    assert result["observations"][0]["arguments"] == selected["arguments"]
    assert result["decision_report"]["status"] == "failed"
    assert result["plan_draft"] is None and result["completion"] == "needs_input"


async def test_invalid_auxiliary_output_is_labeled_and_never_scored_as_success(monkeypatch):
    from ai.runtime import create_runtime
    class BrokenAuxiliary:
        backend = "external"
        calls = 0
        def extract(self, task, stage=1):
            self.calls += 1
            return {}
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    auxiliary = BrokenAuxiliary()
    runtime.auxiliary = auxiliary
    def forbidden(context, candidates):
        raise AssertionError("Invalid extraction reached judge")
    monkeypatch.setattr(runtime.model.backend, "score_candidates", forbidden)
    events = []
    async def sink(event):
        events.append(event)
    try:
        result = await runtime.run(task(), sink)
    finally:
        await runtime.aclose()
    assert auxiliary.calls == 1 and result["constraint_proposals"] == []
    assert result["extraction_report"]["status"] == "failed"
    assert result["extraction_report"]["issue_codes"] == ["auxiliary_invalid_output"]
    assert result["last_processed_message_id"] is None and result["observations"] == []
    assert events[0]["payload"]["extraction_mode"] == "external-structured"
    assert events[0]["payload"]["model_mode"] == "fake"


async def test_ready_plan_without_route_observations_requires_fresh_selected_work():
    from ai.runtime import create_runtime
    value = task()
    value.update(recent_messages=[], questions=[])
    value["current_plan"].update(value["base_versions"], validation="ready")
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture", "max_decision_rounds": 1})
    try:
        result = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    assert result["completion"] == "needs_input" and result["plan_draft"] is None
    assert len(result["observations"]) == 1 and result["observations"][0]["tool_name"] == "get_car_route"
    assert result["decision_report"]["reason"] == "round_limit"


async def test_judge_receives_actual_route_time_and_grounded_observed_prices(monkeypatch):
    from ai.runtime import create_runtime
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture", "max_decision_rounds": 1})
    received = []
    def score(context, candidates):
        received.append((context, candidates))
        return [1., 0.]
    monkeypatch.setattr(runtime.model.backend, "score_candidates", score)
    try:
        result = await runtime.run(task(), None)
    finally:
        await runtime.aclose()
    assert len(received) == 1
    context, candidates = received[0]
    assert candidates[0]["arguments"]["departure_at"] == "2026-11-21T09:00:00+09:00"
    assert context["facts"]["details"]["fixture:place-a"]["menus"][0]["price_krw"] == 10000
    assert result["observations"][0]["arguments"] == candidates[0]["arguments"]
    assert "observations" not in context


def test_code_preparation_keeps_independent_later_day_route_alternatives():
    from ai.decision_candidates import build_decision_candidates
    candidates = build_decision_candidates(task())["candidates"]
    routes = [c for c in candidates if c["tool_name"] == "get_car_route"]
    assert [c["arguments"] for c in routes] == [
        dict(from_ref="anchor:origin", to_ref="fixture:place-a", departure_at="2026-11-21T09:00:00+09:00"),
        dict(from_ref="anchor:lodging", to_ref="anchor:destination", departure_at="2026-11-22T09:00:00+09:00")]


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


async def test_manual_replan_recalculates_instead_of_reusing_old_ready_plan():
    from ai.runtime import create_runtime
    value = task()
    value.update(goal="manual_replan", questions=[], recent_messages=[])
    value["current_plan"].update(value["base_versions"], validation="ready")
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    try:
        result = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    assert [o["tool_name"] for o in result["observations"]] == [
        "get_car_route", "get_car_route", "get_car_route", "get_car_route", "build_itinerary", "calculate_costs"]
    assert result["plan_draft"]["validation"] == "needs_input" and result["completion"] == "needs_input"
    assert result["plan_draft"]["cost"]["total_krw"] is None
    assert value["current_plan"]["cost"]["total_krw"] == 120000
    assert any(q["field"] == "menu_selection" and q["target_ref"] == "item-b" for q in result["questions"])


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
