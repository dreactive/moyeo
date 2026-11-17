from copy import deepcopy
from ai.planning import planned_visits, selected_route_observations
from ai.tools.context import build_tool_context
from ai.questions import question


def cost_line(ref, price, evidence_id=None, scope="shared", assumption=None, category="car"):
    return dict(id=ref, category=category, scope=scope, owner_id=None, description=ref,
                unit_price_krw=price, quantity=1, subtotal_krw=None, paid=False,
                evidence_id=evidence_id, assumption=assumption)


def menu_line(context, visit, menu, questions):
    answer = next((q["answer"] for q in context["questions"] if q["field"] == "menu_selection"
                   and q["target_ref"] == visit["item_id"] and q["status"] == "answered"
                   and q["answer"].get("menu_id") == menu["id"]), None)
    known_basis = "1인" in (menu.get("serving_basis") or "")
    if not answer and not known_basis:
        questions.append(question("menu_selection", visit["item_id"], "메뉴 수량·공유 여부를 선택해주세요."))
    line = cost_line("menu:" + visit["item_id"] + ":" + menu["id"],
                    menu["price_krw"] if answer or known_basis else None, menu["evidence_id"],
                    answer["scope"] if answer else "per_person", "사용자 선택 또는 명시된 1인분 가정", "meal")
    line["quantity"] = answer["quantity"] if answer else 1
    return line


def car_cost_lines(context, fixed_lines):
    descriptions = [str(l.get("description", "")) + " " + str(l.get("assumption") or "")
                    for l in fixed_lines if l.get("category") == "car"]
    extras = [] if any("유류" in d and "주차" in d for d in descriptions) else [
        cost_line("car:extras", None, assumption="유류/주차 비용 확인 필요")]
    if any("통행료" in d and "포함" in d for d in descriptions):
        return extras
    seen = set()
    for observation in selected_route_observations(context):
        leg = observation["result"]
        if leg["evidence_id"] not in seen:
            extras.append(cost_line("toll:" + leg["evidence_id"], leg.get("toll_krw"), leg["evidence_id"],
                                    assumption="통행료만; 유류·주차 별도"))
            seen.add(leg["evidence_id"])
    return extras


def build_cost_inputs(context):
    details = build_tool_context(context)["details"]
    lines = deepcopy(context["config"].get("fixed_costs", []))
    questions = []
    for visit in planned_visits(context):
        detail = details.get(visit["place_ref"], {})
        selected = [m for m in detail.get("menus", []) if m["id"] in visit["selected_menu_ids"]]
        if not selected:
            free = next((e for e in detail.get("evidence", []) if e["field"] == "admission_fee"
                         and e["normalized_value"] == 0 and e["status"] == "api_observed"
                         and e["match_status"] == "matched"), None)
            lines.append(cost_line("visit:" + visit["item_id"], 0 if free else None,
                                   free["id"] if free else None, "per_person", "입장료/메뉴 확인 필요", "admission"))
            if not free:
                questions.append(question("menu_selection", visit["item_id"], "메뉴·이용권 또는 무료 근거를 확인해주세요."))
        lines.extend(menu_line(context, visit, menu, questions) for menu in selected)
    lines.extend(car_cost_lines(context, lines))
    users = [m["user_id"] for m in context["members"]]
    budgets = {u: context["config"].get("per_person_budget_krw") for u in users}
    for constraint in context["constraints"]:
        if (constraint["key"] in ("budget", "budget_krw") and constraint.get("status") == "confirmed"
                and constraint["kind"] == "hard" and constraint["owner_id"] in budgets):
            budgets[constraint["owner_id"]] = constraint["value"]
    return dict(lines=lines, member_ids=users, budget_by_user=budgets), questions
