from ai.questions import question
from copy import deepcopy
from ai.cost_inputs import build_cost_inputs
from ai.context import build_context
from ai.conflicts import conflict
from ai.tools.costs import allocate


def budget_conflicts(task, cost, item_ids):
    arguments = build_cost_inputs(task)[0]
    budgets, users = arguments["budget_by_user"], arguments["member_ids"]
    shares = [allocate(line, users) for line in cost.get("lines", [])]
    conflicts = []
    for user in users:
        delta = cost.get("planned_balance_krw", {}).get(user)
        if delta is None and budgets[user] is not None:
            delta = budgets[user] - sum(s[user] or 0 for s in shares)
        if delta is not None and delta < 0:
            found = conflict("budget", f"{user}의 예산을 최소 {-delta:,}원 초과합니다.", item_ids, task["base_versions"])
            found["id"] = "conflict:budget:" + user
            conflicts.append(found)
    return conflicts


def reuse_current_plan(task, result):
    if task["goal"] == "manual_replan":
        return False
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
    item_ids = list(dict.fromkeys(v["item_id"] for d in itinerary["days"] for v in d["visits"]))
    result["conflicts"].extend(budget_conflicts(task, cost, item_ids))
    if cost["total_krw"] is None:
        result["questions"].append(question("constraint_value", None, "가격/차량 비용 중 미확인 금액이 있습니다."))
    validation = "conflict" if result["conflicts"] else "needs_input" if result["questions"] else "ready"
    result["plan_draft"] = dict(selected_item_ids=[v["item_id"] for d in itinerary["days"] for v in d["visits"]],
                               days=itinerary["days"], cost=cost, validation=validation,
                               blocking_conflict_ids=[c["id"] for c in result["conflicts"] if c["blocking"]])
    result["completion"] = "done" if validation == "ready" else "needs_input"
    return True
