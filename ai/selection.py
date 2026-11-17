from copy import deepcopy
from ai.questions import question
from ai.tools.context import build_tool_context


def apply_selection(task):
    task = deepcopy(task)
    selection = task.get("user_selection")
    if not selection:
        return task, []
    if selection["base_versions"] != task["base_versions"]:
        return task, [question("constraint_value", None, "오래된 선택입니다. 현재 안에서 다시 선택해주세요.")]
    effect = selection["effect"]
    plan = task.get("current_plan") or {}
    ids = {v["item_id"] for d in plan.get("days", []) for v in d["visits"]}
    if effect["kind"] == "drop_visit" and effect["item_id"] in ids:
        for day in plan["days"]:
            day["visits"] = [v for v in day["visits"] if v["item_id"] != effect["item_id"]]
        return task, []
    if effect["kind"] == "reorder_visits":
        day = next((d for d in plan.get("days", []) if d["date"] == effect["date"]), None)
        order = effect["ordered_item_ids"]
        if day and len(order) == len(day["visits"]) and set(order) == {v["item_id"] for v in day["visits"]}:
            day["visits"].sort(key=lambda v: order.index(v["item_id"]))
            for visit in day["visits"]:
                visit["start_at"] = None
            return task, []
    if (effect["kind"] == "replace_place" and effect["item_id"] in ids
            and effect["new_place_ref"] in build_tool_context(task)["places"]):
        for item in plan.get("item_snapshots", []):
            if item["id"] == effect["item_id"]:
                item["place_ref"] = effect["new_place_ref"]
        for day in plan["days"]:
            for visit in day["visits"]:
                if visit["item_id"] == effect["item_id"]:
                    visit.update(place_ref=effect["new_place_ref"], selected_menu_ids=[])
        return task, []
    return task, [question("constraint_value", effect.get("constraint_id"),
                           "조건 소유자의 수정·확인 또는 유효한 선택이 필요합니다.", effect.get("owner_id"))]
