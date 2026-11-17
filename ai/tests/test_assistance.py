from ai.tests.test_place_route_tools import task


def test_rule_assisted_budget_correction_is_owned_and_grounded():
    from ai.assistance import explicit_constraints
    value = task()
    value["constraints"] = [{"id": "budget1", "owner_id": "u1", "key": "budget_krw"}]
    value["recent_messages"] = [dict(id="fix", author_id="u1", text="아니 내 예산은 15만원으로 정정할게")]
    proposals = explicit_constraints(value)
    assert proposals == [dict(owner_id="u1", key="budget_krw", value=150000, kind="hard",
                              source_message_ids=["fix"], replaces_constraint_id="budget1")]
