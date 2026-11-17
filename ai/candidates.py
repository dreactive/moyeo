import math
from ai.tools.validation import PARAMETERS
from ai.planning import pending_routes, planned_visits, itinerary_arguments
from ai.tools.context import build_tool_context
from ai.cost_inputs import build_cost_inputs


def tool_option(name, arguments, reason):
    return dict(action="tool", reason=reason, tool_name=name, arguments=arguments,
                source_message_ids=[], source_refs=[])


def grounded_options(context):
    context = build_tool_context(context)
    options, visits = [], planned_visits(context)
    for visit in visits:
        if visit["place_ref"] not in context["details"]:
            options.append(tool_option("get_place_details", {"place_ref": visit["place_ref"]}, "방문 후보의 실제 가격·시간 조회"))
    routes = pending_routes(context)
    options.extend(tool_option("get_car_route", r, "이 날짜의 아직 조회하지 않은 실제 자동차 구간") for r in routes)
    observed = {o["tool_name"] for o in context["observations"]}
    if not routes and all(v["place_ref"] in context["details"] for v in visits):
        for name, arguments in (("build_itinerary", itinerary_arguments(context)),
                                ("calculate_costs", build_cost_inputs(context)[0])):
            if name not in observed:
                options.append(tool_option(name, arguments, "확보한 관측과 사용자 입력을 코드로 계산"))
    options.append(dict(action="ask", reason="부족하거나 모호한 여행 조건을 확인해주세요.",
                        tool_name=None, arguments={}, source_message_ids=[], source_refs=[]))
    return options


def select_candidate(candidates, scores):
    if not candidates or len(scores) != len(candidates):
        raise ValueError("Candidate score count mismatch")
    if any(isinstance(s, bool) or not isinstance(s, (float, int)) or not math.isfinite(s) for s in scores):
        raise ValueError("Nonfinite or invalid judge score")
    return max(range(len(candidates)), key=scores.__getitem__)


def build_candidates(context):
    messages = {m["id"] for m in context["recent_messages"]}
    refs = {r for o in context["observations"] for r in o.get("source_refs", [])}
    refs.update(context.get("places", {}))
    accepted = []
    required = {"action", "reason", "tool_name", "arguments", "source_message_ids", "source_refs"}
    for c in context.get("generated_candidates", []):
        if not isinstance(c, dict) or set(c) != required:
            continue
        c = dict(c)
        if c["action"] in PARAMETERS and c["tool_name"] == c["action"]:
            c["action"] = "tool"
        if c["action"] not in ("tool", "ask", "direct", "wait", "finish", "unsupported"):
            continue
        if set(c["source_message_ids"]) <= messages and set(c["source_refs"]) <= refs:
            accepted.append(c)
    return accepted
