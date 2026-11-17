from ai.tests.test_place_route_tools import task


def test_stale_selection_never_executes_and_fresh_drop_replans():
    from ai.selection import apply_selection
    value = task()
    value["user_selection"] = {"base_versions": {}, "effect": {"kind": "drop_visit", "item_id": "item-a"}}
    stale, questions = apply_selection(value)
    assert len(stale["current_plan"]["days"][0]["visits"]) == 2 and questions
    value["user_selection"]["base_versions"] = value["base_versions"]
    changed, questions = apply_selection(value)
    assert [v["item_id"] for v in changed["current_plan"]["days"][0]["visits"]] == ["item-b"]
    assert not questions and len(value["current_plan"]["days"][0]["visits"]) == 2
