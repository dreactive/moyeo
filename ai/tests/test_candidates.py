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
