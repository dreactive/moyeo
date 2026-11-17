from ai.tests.test_place_route_tools import task


def test_context_has_twenty_messages_and_structured_answers():
    from ai.context import build_context
    value = task()
    value["recent_messages"] = [dict(id=str(i), author_id="u1", text="hi") for i in range(30)]
    value["questions"] = [dict(field="origin", target_ref="anchor:origin", status="answered",
                               owner_id=None, answered_by="u1", answer={"latitude": 1, "longitude": 2})]
    context = build_context(value, [])
    assert [m["id"] for m in context["recent_messages"]] == [str(i) for i in range(10, 30)]
    assert context["config"]["origin"]["latitude"] == 1
    assert value["config"]["origin"]["latitude"] == 34.76


def test_constraint_owner_and_correction_are_grounded():
    from ai.extraction import validate_extraction
    value = task()
    value["constraints"] = [{"id": "c1", "owner_id": "u1", "key": "budget"}]
    proposal = {"owner_id": "u1", "key": "budget", "value": 200000, "kind": "hard",
                "source_message_ids": ["m0"], "replaces_constraint_id": "c1"}
    output = validate_extraction({"constraint_proposals": [proposal]}, value)
    assert output["constraint_proposals"] == [proposal]
    proposal["owner_id"] = "u2"
    assert not validate_extraction({"constraint_proposals": [proposal]}, value)["constraint_proposals"]


def test_new_client_ref_has_message_grounding():
    from ai.extraction import validate_extraction
    value = task()
    value["items"] = []
    proposal = {"client_ref": "client:m1", "existing_item_id": None, "kind": "place",
                "title": "가상 A식당", "source_message_ids": ["m1"]}
    result = validate_extraction({"item_proposals": [proposal]}, value)
    assert result["item_proposals"] == [proposal]
    proposal["title"] = "없는 장소"
    assert not validate_extraction({"item_proposals": [proposal]}, value)["item_proposals"]
