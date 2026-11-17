import pytest


def test_invalid_scores_never_choose_first_candidate():
    from ai.candidates import select_candidate
    candidates = [{"action": "tool"}, {"action": "ask"}]
    assert select_candidate(candidates, [-2., 3.]) == 1
    for scores in ([1.], [float("nan"), 1.], [1., float("inf")], []):
        with pytest.raises(ValueError):
            select_candidate(candidates, scores)


def test_tool_arguments_require_known_refs_and_positive_quantity():
    from ai.tools.validation import validate_arguments
    context = {"places": {"p": {}}, "observations": [], "config": {}}
    for name, arguments in [
        ("delete_everything", {}), ("get_place_details", {"place_ref": "invented"}),
        ("get_car_route", {"from_ref": "p"}),
        ("calculate_costs", {"lines": [{"quantity": -1}], "member_ids": ["u1"], "budget_by_user": {}}),
    ]:
        with pytest.raises(ValueError):
            validate_arguments(name, arguments, context)


def test_candidates_are_not_padded_and_unknown_sources_rejected():
    from ai.candidates import build_candidates
    context = {"recent_messages": [{"id": "m1"}], "observations": [],
               "generated_candidates": [{"action": "ask", "reason": "missing", "tool_name": None,
                    "arguments": {}, "source_message_ids": ["m1"], "source_refs": []}]}
    assert len(build_candidates(context)) == 1
    context["generated_candidates"][0]["source_message_ids"] = ["invented"]
    assert build_candidates(context) == []


def test_model_cannot_replace_observed_menu_price():
    from copy import deepcopy
    from ai.tests.test_place_route_tools import task
    from ai.cost_inputs import build_cost_inputs
    from ai.tools.context import build_tool_context
    from ai.tools.validation import validate_arguments
    value = task()
    arguments, _ = build_cost_inputs(value)
    forged = deepcopy(arguments)
    next(l for l in forged["lines"] if l["category"] == "meal")["unit_price_krw"] = 1
    with pytest.raises(ValueError):
        validate_arguments("calculate_costs", forged, build_tool_context(value))


def test_model_cannot_invent_route_seconds_in_schedule():
    from ai.tests.test_place_route_tools import task
    from ai.planning import itinerary_arguments
    from ai.tools.validation import validate_arguments
    from ai.tools.context import build_tool_context
    value = task()
    args = itinerary_arguments(value)
    args["route_legs"] = [{"from_ref": "fixture:place-a", "to_ref": "fixture:place-b", "duration_seconds": 1}]
    with pytest.raises(ValueError):
        validate_arguments("build_itinerary", args, build_tool_context(value))
