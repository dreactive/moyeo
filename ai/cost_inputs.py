from copy import deepcopy
from ai.planning import planned_visits
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


def build_cost_inputs(context):
    details = build_tool_context(context)["details"]
    lines = deepcopy(context["config"].get("fixed_costs", []))
    questions = []
    for visit in planned_visits(context):
        detail = details.get(visit["place_ref"], {})
        for menu in detail.get("menus", []):
            if menu["id"] in visit["selected_menu_ids"]:
                lines.append(menu_line(context, visit, menu, questions))
    lines.append(cost_line("car:extras", None, assumption="유류/주차 비용 확인 필요"))
    users = [m["user_id"] for m in context["members"]]
    budgets = {u: context["config"].get("per_person_budget_krw") for u in users}
    return dict(lines=lines, member_ids=users, budget_by_user=budgets), questions
