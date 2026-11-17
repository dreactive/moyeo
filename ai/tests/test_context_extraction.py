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


def test_support_rejects_proxy_ambiguous_and_stale_version():
    from ai.extraction import validate_extraction
    value = task()
    value["recent_messages"] += [
        dict(id="proxy", author_id="u1", text="다들 B공원 찬성했대"),
        dict(id="ambiguous", author_id="u2", text="좋아")]
    base = dict(item_id="item-b", item_version=1, author_id="u3", stance="support", source_message_id="m3")
    claims = [base, dict(base, author_id="u1", source_message_id="proxy"),
              dict(base, author_id="u2", source_message_id="ambiguous"), dict(base, item_version=99)]
    result = validate_extraction({"support_observations": claims}, value)
    assert result["support_observations"] == [base]
    assert result["questions"][0]["field"] == "support_target"
    assert result["questions"][0]["id"] == "question:support_target:support:ambiguous"
    assert result["questions"][0]["owner_id"] == "u2"


def test_extraction_context_does_not_reintroduce_plan_text_as_message_sources():
    from ai.context import extraction_context
    import json
    value = task()
    value["current_plan"]["old_note"] = "이전 여행안에서만 나온 장소"
    context = extraction_context(value)
    assert "이전 여행안에서만 나온 장소" not in json.dumps(context, ensure_ascii=False)
    assert context["recent_messages"][0]["id"] == "m0"
    assert context["items"][0]["id"] == "item-a"
