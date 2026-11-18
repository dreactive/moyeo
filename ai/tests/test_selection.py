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


async def test_selected_drop_executes_revised_routes_and_recalculates_selected_visits():
    from ai.runtime import create_runtime
    value = task()
    value["user_selection"] = {"base_versions": value["base_versions"],
        "effect": {"kind": "drop_visit", "item_id": "item-a"}}
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    try:
        result = await runtime.run(value, None)
    finally:
        await runtime.aclose()
    routes = [o for o in result["observations"] if o["tool_name"] == "get_car_route"]
    assert [o["arguments"] for o in routes] == [
        dict(from_ref="anchor:origin", to_ref="fixture:place-b", departure_at="2026-11-21T09:00:00+09:00"),
        dict(from_ref="fixture:place-b", to_ref="anchor:lodging", departure_at="2026-11-21T15:00:00+09:00"),
        dict(from_ref="anchor:lodging", to_ref="anchor:destination", departure_at="2026-11-22T09:00:00+09:00")]
    assert [o["tool_name"] for o in result["observations"][-2:]] == ["build_itinerary", "calculate_costs"]
    assert result["plan_draft"]["selected_item_ids"] == ["item-b"]
    assert all(v["item_id"] == "item-b" for d in result["plan_draft"]["days"] for v in d["visits"])
    assert result["completion"] == "needs_input" and result["plan_draft"]["cost"]["total_krw"] is None
    assert value["current_plan"]["selected_item_ids"] == ["item-a", "item-b"]
