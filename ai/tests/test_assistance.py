from ai.tests.test_place_route_tools import task


def test_rule_assisted_budget_correction_is_owned_and_grounded():
    from ai.assistance import explicit_constraints
    value = task()
    value["constraints"] = [{"id": "budget1", "owner_id": "u1", "key": "budget_krw"}]
    value["recent_messages"] = [dict(id="fix", author_id="u1", text="아니 내 예산은 15만원으로 정정할게")]
    proposals = explicit_constraints(value)
    assert proposals == [dict(owner_id="u1", key="budget_krw", value=150000, kind="hard",
                              source_message_ids=["fix"], replaces_constraint_id="budget1")]


def test_explicit_return_time_keeps_owner_and_does_not_relax_other_constraint():
    from ai.assistance import explicit_constraints
    value = task()
    value["constraints"] = [{"id": "other", "owner_id": "u2", "key": "return_by", "value": "15:00"}]
    value["recent_messages"] = [dict(id="deadline", author_id="u1", text="난 16시까지 역에 도착해야 해")]
    proposal = explicit_constraints(value)[0]
    assert proposal["key"] == "return_by" and proposal["value"] == "16:00"
    assert proposal["owner_id"] == "u1" and proposal["replaces_constraint_id"] is None
