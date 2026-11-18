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


def test_unresolved_items_block_even_canonical_empty_calculations():
    from ai.planning import itinerary_arguments
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.context import build_tool_context
    from ai.tools.validation import validate_arguments
    value = unresolved_task()
    for name, args in (("build_itinerary", itinerary_arguments(value)), ("calculate_costs", build_cost_inputs(value)[0])):
        with pytest.raises(ValueError):
            validate_arguments(name, args, build_tool_context(value))


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
