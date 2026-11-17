import pytest


def test_invalid_scores_never_choose_first_candidate():
    from ai.candidates import select_candidate
    candidates = [{"action": "tool"}, {"action": "ask"}]
    assert select_candidate(candidates, [-2., 3.]) == 1
    for scores in ([1.], [float("nan"), 1.], [1., float("inf")], []):
        with pytest.raises(ValueError):
            select_candidate(candidates, scores)
