from ai.questions import question
from copy import deepcopy
from ai.cost_inputs import build_cost_inputs
from ai.context import build_context
from ai.conflicts import conflict
from ai.tools.costs import allocate
from ai.planning import planned_visits, itinerary_arguments, planning_inputs_ready, selected_place_items
from ai.tools.context import build_tool_context
from ai.tools.hours import validate_hours
from ai.tools.validation import same_arguments

SUPPORTED_HARD_KEYS = ("budget", "budget_krw", "return_by")


def hard_proposals_pending(task, result):
    for proposal in result["constraint_proposals"]:
        if proposal["kind"] != "hard":
            continue
        family = ("budget", "budget_krw") if proposal["key"] in ("budget", "budget_krw") else (proposal["key"],)
        confirmed = any(c.get("status") == "confirmed" and c["kind"] == "hard" and
                        c["owner_id"] == proposal["owner_id"] and c["key"] in family and c["value"] == proposal["value"]
                        for c in task["constraints"])
        if not confirmed:
            return True
    return False


def budget_conflicts(task, cost, item_ids, arguments):
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
             and not task.get("user_selection") and not any(q["status"] == "open" for q in task["questions"])
             and not any(c["kind"] == "hard" and c.get("status") != "superseded" and
                         (c.get("status") != "confirmed" or c["key"] not in SUPPORTED_HARD_KEYS) for c in task["constraints"]))
    if changed or not valid:
        return False
    keys = ("selected_item_ids", "days", "cost", "validation", "blocking_conflict_ids",
            "unplaced_items", "missing_observations")
    result["plan_draft"] = {k: deepcopy(plan[k]) for k in keys if k in plan}
    result["completion"] = "done"
    return True


def assemble_result(task, result):
    actual = [o for o in result["observations"] if o["tool_name"] in ("build_itinerary", "calculate_costs")]
    if not actual:
        return False
    context = build_tool_context(build_context(task, result["observations"]))
    called = {o["tool_name"] for o in actual}
    expected = {}
    if "build_itinerary" in called:
        expected["build_itinerary"] = itinerary_arguments(context)
    if "calculate_costs" in called:
        cost_args, cost_questions = build_cost_inputs(context)
        expected["calculate_costs"] = cost_args
    calculations = {o["tool_name"]: o["result"] for o in actual
                    if same_arguments(o.get("arguments"), expected[o["tool_name"]])}
    result["partial_results"] = deepcopy(calculations)
    if not {"build_itinerary", "calculate_costs"} <= calculations.keys():
        return False
    itinerary, cost = (calculations[k] for k in ("build_itinerary", "calculate_costs"))
    known_ids = [i["id"] for i in selected_place_items(context)]
    scheduled_ids = [v["item_id"] for d in itinerary["days"] for v in d["visits"] if v["item_id"] in known_ids]
    item_ids = list(dict.fromkeys([*scheduled_ids, *known_ids]))
    for found in itinerary["conflicts"] + budget_conflicts(task, cost, item_ids, cost_args):
        if found not in result["conflicts"]:
            result["conflicts"].append(found)
    for found in itinerary["questions"] + cost_questions:
        if found not in result["questions"]:
            result["questions"].append(found)
    for condition in task["constraints"]:
        if condition["kind"] == "hard" and condition.get("status") != "superseded" and (
                condition.get("status") != "confirmed" or condition["key"] not in SUPPORTED_HARD_KEYS):
            found = question("constraint_value", condition["id"],
                             "이 필수 조건의 확인 또는 충족 근거가 더 필요합니다.", condition["owner_id"])
            if found not in result["questions"]:
                result["questions"].append(found)
    actual = [(v["item_id"], v["place_ref"], v["date"]) for d in itinerary["days"] for v in d["visits"]]
    wanted = [(v["item_id"], v["place_ref"], v["date"]) for v in planned_visits(context)]
    legs = [r for d in itinerary["days"] for r in d["route_legs"]]
    complete = (planning_inputs_ready(context) and sorted(actual) == sorted(wanted)
                and legs == expected["build_itinerary"]["route_legs"]
                and not itinerary.get("unplaced_items") and not itinerary.get("missing_observations")
                and not any(any(validate_hours(v, context["details"].get(v["place_ref"], {}), task["base_versions"]))
                            for d in itinerary["days"] for v in d["visits"]))
    pending = result["questions"] or cost["total_krw"] is None or not complete or hard_proposals_pending(task, result)
    validation = "conflict" if result["conflicts"] else "needs_input" if pending else "ready"
    result["plan_draft"] = dict(selected_item_ids=item_ids,
                               days=itinerary["days"], cost=cost, validation=validation,
                               blocking_conflict_ids=[c["id"] for c in result["conflicts"] if c["blocking"]])
    for key in ("unplaced_items", "missing_observations"):
        if itinerary.get(key):
            result["plan_draft"][key] = deepcopy(itinerary[key])
    result["completion"] = "done" if validation == "ready" else "needs_input"
    return True
