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


def test_reorder_replace_and_change_constraint_keep_ownership():
    from ai.selection import apply_selection
    value = task()
    def selected(effect):
        return apply_selection(dict(value, user_selection={"base_versions": value["base_versions"], "effect": effect}))
    changed, questions = selected({"kind": "reorder_visits", "date": "2026-11-21", "ordered_item_ids": ["item-b", "item-a"]})
    assert [v["item_id"] for v in changed["current_plan"]["days"][0]["visits"]] == ["item-b", "item-a"]
    changed, questions = selected({"kind": "replace_place", "item_id": "item-a", "new_place_ref": "fixture:place-b"})
    assert changed["current_plan"]["item_snapshots"][0]["place_ref"] == "fixture:place-b"
    changed, questions = selected({"kind": "change_constraint", "constraint_id": "c1", "owner_id": "u1", "new_value": "18:00"})
    assert questions[0]["owner_id"] == "u1" and changed["constraints"] == value["constraints"]
