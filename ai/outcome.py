from ai.questions import question


def assemble_result(task, result):
    calculations = {o["tool_name"]: o["result"] for o in result["observations"]}
    if not {"build_itinerary", "calculate_costs"} <= calculations.keys():
        return False
    itinerary, cost = (calculations[k] for k in ("build_itinerary", "calculate_costs"))
    result["conflicts"].extend(itinerary["conflicts"])
    result["questions"].extend(itinerary["questions"])
    if cost["total_krw"] is None:
        result["questions"].append(question("constraint_value", None, "가격/차량 비용 중 미확인 금액이 있습니다."))
    validation = "conflict" if result["conflicts"] else "needs_input" if result["questions"] else "ready"
    result["plan_draft"] = dict(selected_item_ids=[v["item_id"] for d in itinerary["days"] for v in d["visits"]],
                               days=itinerary["days"], cost=cost, validation=validation,
                               blocking_conflict_ids=[c["id"] for c in result["conflicts"] if c["blocking"]])
    result["completion"] = "done" if validation == "ready" else "needs_input"
    return True
