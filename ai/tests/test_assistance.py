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


def test_support_assistance_never_creates_proxy_or_ambiguous_votes():
    from ai.assistance import explicit_support
    value = task()
    value["recent_messages"] += [dict(id="proxy", author_id="u1", text="다들 B공원 찬성했대"),
                                 dict(id="unclear", author_id="u2", text="좋아")]
    claims, questions = explicit_support(value, value["items"])
    assert any(c["author_id"] == "u3" and c["source_message_id"] == "m3" for c in claims)
    assert not any(c["source_message_id"] in ("proxy", "unclear") for c in claims)
    assert questions[0]["id"] == "question:support_target:support:unclear"


def test_empty_model_extraction_is_assisted_without_claiming_model_quality():
    from ai.assistance import assist_extraction
    output = assist_extraction({}, task())
    assert output["constraint_proposals"][0]["value"] == 200000
    assert output["constraint_proposals"][0]["key"] == "budget_krw"
    assert any(s["author_id"] == "u3" for s in output["support_observations"])
    assert output["questions"] == []


def test_first_named_place_mention_has_consistent_client_ref_and_support():
    from ai.assistance import assist_extraction
    value = task()
    value["items"] = []
    value["current_plan"] = None
    value["recent_messages"] = [dict(id="new", author_id="u1", text="오동도 가자")]
    output = assist_extraction({}, value)
    assert output["item_proposals"][0]["title"] == "오동도"
    assert output["item_proposals"][0]["client_ref"] == output["support_observations"][0]["item_id"] == "client:new"


def test_question_form_mention_creates_item_but_never_support():
    from ai.assistance import assist_extraction
    value = task()
    value["recent_messages"] = [dict(id="mention", author_id="u1", text="가상 A식당?")]
    assert assist_extraction({}, value)["support_observations"] == []
    value["items"] = []
    output = assist_extraction({}, value)
    assert output["item_proposals"][0]["title"] == "가상 A식당"
    assert output["support_observations"] == []
