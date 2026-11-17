from ai.tests.test_place_route_tools import task


def test_question_targets_must_match_the_contract_domain():
    from ai.questions import valid_questions, question
    value = task()
    candidates = [question("constraint_value", None, "error"),
                  question("constraint_value", "item-a", "hours missing"),
                  question("visit_duration", "item-a", "stay?"),
                  question("origin", "anchor:origin", "origin?")]
    assert [q["field"] for q in valid_questions(value, candidates)] == ["visit_duration", "origin"]
