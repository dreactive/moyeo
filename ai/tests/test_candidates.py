import pytest


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


def test_explicit_registered_tool_action_can_be_normalized_without_inventing_args():
    from ai.candidates import build_candidates
    value = {"recent_messages": [], "observations": [], "generated_candidates": [
        dict(action="get_place_details", reason="lookup", tool_name="get_place_details",
             arguments={"place_ref": "observed:p"}, source_message_ids=[], source_refs=[])]}
    assert build_candidates(value)[0]["action"] == "tool"
    value["generated_candidates"][0]["tool_name"] = "delete_everything"
    assert build_candidates(value) == []


def test_grounded_choices_include_independent_routes_and_ask():
    from ai.candidates import grounded_options
    from ai.tests.test_place_route_tools import task
    options = grounded_options(task())
    routes = [c for c in options if c["tool_name"] == "get_car_route"]
    assert {c["arguments"]["from_ref"] for c in routes} == {"anchor:origin", "anchor:lodging"}
    assert any(c["action"] == "ask" for c in options)
    assert all(c["tool_name"] != "calculate_costs" for c in options)


def test_invalid_or_already_observed_tools_are_excluded_from_candidates():
    from ai.candidates import valid_options, tool_option
    from ai.tests.test_place_route_tools import task
    options = [
        tool_option("get_place_details", {"place_ref": "fixture:place-a"}, "already known"),
        tool_option("get_place_details", {"place_ref": "invented"}, "invalid"),
        tool_option("search_places", {"query": "", "region": "여수", "category": None}, "empty")]
    assert valid_options(task(), options) == []
