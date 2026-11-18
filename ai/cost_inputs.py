from copy import deepcopy
import re

from ai.planning import missing_visit_locations, planned_visits, route_inputs, selected_place_items
from ai.tools.context import build_tool_context
from ai.questions import question


def cost_line(ref, price, evidence_id=None, scope="shared", assumption=None, category="car"):
    return dict(id=ref, category=category, scope=scope, owner_id=None, description=ref,
                unit_price_krw=price, quantity=1, subtotal_krw=None, paid=False,
                evidence_id=evidence_id, assumption=assumption)


def menu_line(context, visit, menu, questions):
    answer = next((q["answer"] for q in context["questions"] if q["field"] == "menu_selection"
                   and q["target_ref"] == visit["item_id"] and q["status"] == "answered"
                   and q.get("owner_id") in (None, q.get("answered_by"))
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
    inclusions = [clause for line in fixed_lines if line.get("category") == "car" and line.get("unit_price_krw") is not None
                  for value in (line.get("description"), line.get("assumption"))
                  for clause in re.split(r"[.,;]", value or "")
                  if re.search(r"(?<![미불])포함(?!\s*(?:안|아님|없|되지|하지))", clause)]
    included = {fee for fee in ("유류", "주차", "통행료") for clause in inclusions
                if fee in clause and not re.search(fee + r"(?:비|비용)?\s*(?:별도|제외|미포함|불포함)", clause)}
    extras = [] if {"유류", "주차"} <= included else [
        cost_line("car:extras", None, assumption="유류/주차 비용 확인 필요")]
    if "통행료" in included:
        return extras
    extras.extend(cost_line("toll:unobserved:visit:" + item["item_id"], None, assumption="미배치 장소의 이동 구간 통행료 미조회")
                  for item in missing_visit_locations(context, planned_visits(context)))
    routes = list(route_inputs(context))
    if not routes:
        return extras + [cost_line("toll:unobserved:trip", None, assumption="이동 구간 통행료 미조회")]
    seen = set()
    for day, args, visit, observation in routes:
        if observation is None:
            ref = f"toll:unobserved:{day}:{args['from_ref']}:{args['to_ref']}"
            if visit:
                ref += ":" + visit["item_id"]
            extras.append(cost_line(ref, None, assumption="이동 구간 통행료 미조회"))
            continue
        leg = observation["result"]
        evidence_id = leg.get("evidence_id")
        ref = "toll:" + evidence_id if evidence_id else f"toll:unobserved:{day}:{args['from_ref']}:{args['to_ref']}"
        if ref in seen:
            ref += ":" + args["departure_at"]
        seen.add(ref)
        extras.append(cost_line(ref, leg.get("toll_krw") if evidence_id else None, evidence_id,
                                assumption="통행료만; 유류·주차 별도"))
    return extras


def build_cost_inputs(context):
    context = build_tool_context(context)
    details = context["details"]
    lines = deepcopy(context["config"].get("fixed_costs", []))
    questions = []
    visits = planned_visits(context)
    for visit in visits:
        detail = details.get(visit["place_ref"], {})
        selected = [m for m in detail.get("menus", []) if m["id"] in visit["selected_menu_ids"]]
        if not selected:
            free = next((e for e in detail.get("evidence", []) if e["field"] == "admission_fee"
                         and type(e["normalized_value"]) is int and e["normalized_value"] == 0
                         and e["status"] == "api_observed"
                         and e["match_status"] == "matched"), None)
            lines.append(cost_line("visit:" + visit["item_id"], 0 if free else None,
                                   free["id"] if free else None, "per_person", "입장료/메뉴 확인 필요", "admission"))
            if not free and detail.get("menus"):
                questions.append(question("menu_selection", visit["item_id"], "메뉴·이용권 또는 무료 근거를 확인해주세요."))
        lines.extend(menu_line(context, visit, menu, questions) for menu in selected)
    resolved = {v["item_id"] for v in visits}
    for item in selected_place_items(context):
        if item["id"] not in resolved:
            lines.append(cost_line("visit:" + item["id"], None, scope="per_person",
                                   assumption="방문 장소 미확인", category="admission"))
    lines.extend(car_cost_lines(context, lines))
    users = [m["user_id"] for m in context["members"]]
    budgets = {u: context["config"].get("per_person_budget_krw") for u in users}
    for constraint in context["constraints"]:
        if (constraint["key"] in ("budget", "budget_krw") and constraint.get("status") == "confirmed"
                and constraint["kind"] == "hard" and constraint["owner_id"] in budgets):
            budgets[constraint["owner_id"]] = constraint["value"]
    return dict(lines=lines, member_ids=users, budget_by_user=budgets), questions


def cost_inputs_ready(context, arguments=None):
    args = arguments if arguments is not None else build_cost_inputs(context)[0]
    users = args["member_ids"]
    known_amount = any(line["unit_price_krw"] is not None for line in args["lines"])
    explicit_scope = any(r.get('intent')=='cost_estimate' and r.get('operation')=='request'
                         and r.get('status') in ('resolved','pending','needs_input')
                         for r in context.get('_active_requests', []))
    return bool((known_amount or explicit_scope and args['lines']) and users and len(users) == len(set(users))
                and all(type(args["budget_by_user"].get(user)) is int and args["budget_by_user"][user] >= 0 for user in users))
