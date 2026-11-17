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
