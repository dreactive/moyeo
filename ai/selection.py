from copy import deepcopy
from ai.questions import question


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
    return task, [question("constraint_value", effect.get("constraint_id"),
                           "조건 소유자의 수정·확인 또는 유효한 선택이 필요합니다.", effect.get("owner_id"))]
