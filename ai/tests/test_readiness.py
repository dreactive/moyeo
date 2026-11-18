import pytest
from ai.tests.test_place_route_tools import task


def unresolved_task():
    from ai.providers.fixture import fixture_route
    value = task()
    value.update(current_plan=None, observations=[], questions=[],
                 items=[dict(id="unresolved", kind="place", title="가상 A식당", item_version=1)])
    value["config"]["fixed_costs"].append(dict(value["config"]["fixed_costs"][0],
        id="car", category="car", description="유류·주차 포함", unit_price_krw=10000, paid=False))
    for a, b, date in (("anchor:origin", "anchor:lodging", "2026-11-21"),
                       ("anchor:lodging", "anchor:destination", "2026-11-22")):
        args = dict(from_ref=a, to_ref=b, departure_at=date + "T09:00:00+09:00")
        value["observations"].append(dict(tool_name="get_car_route", arguments=args, result=fixture_route(value, args)))
    return value


def test_unresolved_items_prevent_empty_itinerary_but_allow_partial_costs():
    from ai.planning import itinerary_arguments
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.context import build_tool_context
    from ai.tools.validation import validate_arguments
    value = unresolved_task()
    context = build_tool_context(value)
    with pytest.raises(ValueError):
        validate_arguments("build_itinerary", itinerary_arguments(value), context)
    validate_arguments("calculate_costs", build_cost_inputs(value)[0], context)


def test_assembly_independently_refuses_empty_plan_for_unresolved_item():
    from ai.planning import itinerary_arguments
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.itinerary import build_itinerary
    from ai.tools.costs import calculate_costs
    from ai.outcome import assemble_result
    from ai.result import empty_result
    value = unresolved_task()
    result = empty_result(value)
    itinerary, costs = itinerary_arguments(value), build_cost_inputs(value)[0]
    result["observations"] = [
        dict(tool_name="build_itinerary", arguments=itinerary, result=build_itinerary(**itinerary, config=value["config"])),
        dict(tool_name="calculate_costs", arguments=costs, result=calculate_costs(**costs))]
    assemble_result(value, result)
    assert result["completion"] == "needs_input" and result["plan_draft"]["validation"] != "ready"


async def test_chosen_partial_calculations_are_retained_and_unplaced_item_stays_selected():
    from ai.cost_inputs import build_cost_inputs
    from ai.outcome import assemble_result
    from ai.planning import itinerary_arguments, next_route
    from ai.result import empty_result
    from ai.tools.registry import RegisteredTools
    from ai.providers.fixture import fixture_route
    value = task()
    value["questions"] = []
    place = value["observations"][0]["result"]["place"]
    value["observations"][0] = dict(tool_name="search_places", arguments={}, result=dict(places=[place]))
    route = next_route(value)
    value["observations"].append(dict(tool_name="get_car_route", arguments=route, result=fixture_route(value, route)))
    tools = RegisteredTools(value)
    cost_args = build_cost_inputs(value)[0]
    cost = await tools.execute("calculate_costs", cost_args)
    assert cost["known_total_krw"] == 80000 and cost["total_krw"] is None
    assert any(line["id"].startswith("toll:unobserved:") and line["subtotal_krw"] is None for line in cost["lines"])
    result = empty_result(value)
    result["observations"] = [dict(tool_name="calculate_costs", arguments=cost_args, result=cost)]
    assert not assemble_result(value, result)
    assert result["partial_results"] == {"calculate_costs": cost}
    itinerary_args = itinerary_arguments(value)
    itinerary = await tools.execute("build_itinerary", itinerary_args)
    assert [v["item_id"] for v in itinerary["days"][0]["visits"]] == ["item-a"]
    assert itinerary["unplaced_items"] == [dict(item_id="item-b", place_ref="fixture:place-b", reason="missing_route")]
    assert any(gap["field"] == "opening_hours" and gap["item_id"] == "item-a" for gap in itinerary["missing_observations"])
    assert not itinerary["questions"]
    result["observations"].append(dict(tool_name="build_itinerary", arguments=itinerary_args, result=itinerary))
    assert assemble_result(value, result)
    assert result["partial_results"] == {"calculate_costs": cost, "build_itinerary": itinerary}
    assert result["plan_draft"]["selected_item_ids"] == ["item-a", "item-b"]
    assert result["plan_draft"]["validation"] == "needs_input"


def test_excluded_place_does_not_affect_planned_visits_or_cost_inputs():
    from ai.cost_inputs import build_cost_inputs
    from ai.planning import planned_visits
    value = task()
    value["items"][0]["state"] = "excluded"
    assert [v["item_id"] for v in planned_visits(value)] == ["item-b"]
    assert not any("item-a" in line["id"] for line in build_cost_inputs(value)[0]["lines"])


def test_unknown_cost_placeholders_alone_cannot_displace_place_research():
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.context import build_tool_context
    from ai.tools.validation import validate_arguments
    value = unresolved_task()
    value["observations"] = []
    value["config"]["fixed_costs"] = []
    with pytest.raises(ValueError, match="cost scope"):
        validate_arguments("calculate_costs", build_cost_inputs(value)[0], build_tool_context(value))


async def test_fixed_cost_partial_results_can_be_calculated_before_trip_dates_exist():
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.registry import RegisteredTools
    value = task()
    value.update(current_plan=None, items=[], observations=[])
    value["config"].update(start_date=None, end_date=None)
    arguments, _ = build_cost_inputs(value)
    result = await RegisteredTools(value).execute("calculate_costs", arguments)
    assert result["known_total_krw"] == 80000 and result["total_krw"] is None
    assert any(row["id"] == "toll:unobserved:trip" for row in result["lines"])


async def test_partial_cost_observation_is_not_published_after_new_price_facts():
    from ai.cost_inputs import build_cost_inputs
    from ai.outcome import assemble_result
    from ai.result import empty_result
    from ai.tools.registry import RegisteredTools
    value = task()
    new_detail = value["observations"].pop(0)
    arguments, _ = build_cost_inputs(value)
    initial_cost = await RegisteredTools(value).execute("calculate_costs", arguments)
    result = empty_result(value)
    result["observations"] = [dict(tool_name="calculate_costs", arguments=arguments, result=initial_cost), new_detail]
    assert not assemble_result(value, result)
    assert result["partial_results"] == {}
    assert len(result["observations"]) == 2


async def test_itinerary_basis_invalidates_obsolete_unplaced_and_missing_hours_results():
    from ai.outcome import assemble_result
    from ai.planning import itinerary_arguments, next_route
    from ai.providers.fixture import fixture_route
    from ai.result import empty_result
    from ai.tools.registry import RegisteredTools
    value = task()
    detail = value["observations"][0]
    value["observations"][0] = dict(tool_name="search_places", arguments={}, result=dict(places=[detail["result"]["place"]]))
    route = next_route(value)
    value["observations"].append(dict(tool_name="get_car_route", arguments=route, result=fixture_route(value, route)))
    arguments = itinerary_arguments(value)
    itinerary = await RegisteredTools(value).execute("build_itinerary", arguments)
    assert any(missing["field"] == "opening_hours" for missing in itinerary["missing_observations"])
    assert itinerary_arguments(dict(value, observations=[*value["observations"], detail])) != arguments
    assert itinerary_arguments(dict(value, config=dict(value["config"], day_end_time="17:00"))) != arguments
    value["items"].append(dict(id="item-c", kind="place", title="미확인 장소", item_version=1))
    value["_new_item_refs"] = ["item-c"]
    assert itinerary_arguments(value) != arguments
    result = empty_result(value)
    result["observations"] = [dict(tool_name="build_itinerary", arguments=arguments, result=itinerary), detail]
    assert not assemble_result(value, result)
    assert result["partial_results"] == {}
    current = dict(value, observations=[*value["observations"], detail])
    current_itinerary = await RegisteredTools(current).execute("build_itinerary", itinerary_arguments(current))
    assert dict(item_id="item-c", place_ref=None, reason="unresolved_place") in current_itinerary["unplaced_items"]
    assert not any(missing["field"] == "opening_hours" for missing in current_itinerary["missing_observations"])


async def test_unresolved_visit_does_not_block_a_later_identified_visit():
    from ai.cost_inputs import build_cost_inputs
    from ai.planning import itinerary_arguments, next_route
    from ai.providers.fixture import fixture_route
    from ai.tools.registry import RegisteredTools
    value = task()
    value["observations"].pop(0)
    route = next_route(value)
    assert route["to_ref"] == "fixture:place-b"
    value["observations"].append(dict(tool_name="get_car_route", arguments=route, result=fixture_route(value, route)))
    result = await RegisteredTools(value).execute("build_itinerary", itinerary_arguments(value))
    assert [v["item_id"] for v in result["days"][0]["visits"]] == ["item-b"]
    assert result["unplaced_items"] == [dict(item_id="item-a", place_ref=None, reason="unresolved_place")]
    assert any(line["id"] == "toll:unobserved:visit:item-a" for line in build_cost_inputs(value)[0]["lines"])



async def test_same_run_new_hard_proposal_cannot_be_ready_before_owner_confirmation():
    from ai.runtime import create_runtime
    value = task()
    value.update(questions=[], recent_messages=[], goal="manual_replan")
    value["current_plan"]["selected_item_ids"] = ["item-a"]
    value["current_plan"]["days"][0]["visits"] = value["current_plan"]["days"][0]["visits"][:1]
    value["config"]["fixed_costs"].append(dict(value["config"]["fixed_costs"][0],
        id="car", category="car", description="유류·주차 포함", unit_price_krw=10000, paid=False))
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    try:
        control = await runtime.run(value, None)
        value["recent_messages"] = [dict(id="new", author_id="u1", text="내 예산은 1만원")]
        result = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    assert control["completion"] == "done" and control["plan_draft"]["validation"] == "ready"
    assert control["plan_draft"]["cost"]["total_krw"] == 130000 and not control["questions"]
    assert result["completion"] == "needs_input" and result["plan_draft"]["validation"] == "needs_input"
    assert result["constraint_proposals"][0]["value"] == 10000
    proposal = result["constraint_proposals"][0]
    assert proposal["owner_id"] == "u1" and proposal["source_message_ids"] == ["new"] and proposal["kind"] == "hard"
    assert all(not (q.get("target_ref") or "").startswith("pending:") for q in result["questions"])
    costs = next(o for o in result["observations"] if o["tool_name"] == "calculate_costs")
    assert costs["arguments"]["budget_by_user"]["u1"] == 200000
    assert result["plan_draft"]["cost"]["total_krw"] == 130000
