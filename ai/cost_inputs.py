from copy import deepcopy
from ai.planning import planned_visits
from ai.tools.context import build_tool_context
from ai.questions import question


def cost_line(ref, price, evidence_id=None, scope="shared", assumption=None, category="car"):
    return dict(id=ref, category=category, scope=scope, owner_id=None, description=ref,
                unit_price_krw=price, quantity=1, subtotal_krw=None, paid=False,
                evidence_id=evidence_id, assumption=assumption)


def build_cost_inputs(context):
    details = build_tool_context(context)["details"]
    lines = deepcopy(context["config"].get("fixed_costs", []))
    questions = []
    for visit in planned_visits(context):
        detail = details.get(visit["place_ref"], {})
        for menu in detail.get("menus", []):
            if menu["id"] in visit["selected_menu_ids"]:
                lines.append(cost_line("menu:" + visit["item_id"] + ":" + menu["id"], menu["price_krw"],
                    menu["evidence_id"], "per_person", "명시된 1인 메뉴 1개", "meal"))
    lines.append(cost_line("car:extras", None, assumption="유류/주차 비용 확인 필요"))
    users = [m["user_id"] for m in context["members"]]
    budgets = {u: context["config"].get("per_person_budget_krw") for u in users}
    return dict(lines=lines, member_ids=users, budget_by_user=budgets), questions
