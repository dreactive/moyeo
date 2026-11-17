from ai.questions import question
from copy import deepcopy
from ai.cost_inputs import build_cost_inputs
from ai.context import build_context


def reuse_current_plan(task, result):
    plan = task.get("current_plan") or {}
    changed = any(result[k] for k in ("constraint_proposals", "item_proposals", "support_observations", "questions"))
    valid = (plan.get("validation") == "ready" and plan.get("cost", {}).get("total_krw") is not None
             and all(plan.get(k) == v for k, v in task["base_versions"].items())
             and not task.get("user_selection") and not any(q["status"] == "open" for q in task["questions"]))
    if changed or not valid:
        return False
    keys = ("selected_item_ids", "days", "cost", "validation", "blocking_conflict_ids")
    result["plan_draft"] = {k: deepcopy(plan[k]) for k in keys}
    result["completion"] = "done"
    return True


def assemble_result(task, result):
    calculations = {o["tool_name"]: o["result"] for o in result["observations"]}
    if not {"build_itinerary", "calculate_costs"} <= calculations.keys():
        return False
    itinerary, cost = (calculations[k] for k in ("build_itinerary", "calculate_costs"))
    result["conflicts"].extend(itinerary["conflicts"])
    result["questions"].extend(itinerary["questions"])
    result["questions"].extend(build_cost_inputs(build_context(task, result["observations"]))[1])
    if cost["total_krw"] is None:
        result["questions"].append(question("constraint_value", None, "가격/차량 비용 중 미확인 금액이 있습니다."))
    validation = "conflict" if result["conflicts"] else "needs_input" if result["questions"] else "ready"
    result["plan_draft"] = dict(selected_item_ids=[v["item_id"] for d in itinerary["days"] for v in d["visits"]],
                               days=itinerary["days"], cost=cost, validation=validation,
                               blocking_conflict_ids=[c["id"] for c in result["conflicts"] if c["blocking"]])
    result["completion"] = "done" if validation == "ready" else "needs_input"
    return True
