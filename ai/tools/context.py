from copy import deepcopy

from ai.providers.live import current_place_details, detail_matches_place, recent_detail_attempt


def build_tool_context(context):
    ctx = deepcopy(context)
    ctx["places"], ctx["details"], ctx["detail_attempts"] = {}, {}, {}
    for name in ("origin", "destination", "lodging"):
        if ctx["config"].get(name):
            ctx["places"]["anchor:" + name] = ctx["config"][name]
    details = {}
    for observation in ctx.get("observations", []):
        result = observation["result"]
        for place in result.get("places", []):
            ctx["places"][place["id"]] = place
        if "place" in result:
            details[result["place"]["id"]] = result
    for ref, detail in details.items():
        place = ctx["places"].setdefault(ref, detail["place"])
        current = current_place_details(detail, place, ctx["config"], ctx.get("_provider_mode"))
        if current is not None:
            ctx["details"][ref] = current
            ctx["detail_attempts"][ref] = current
        elif recent_detail_attempt(detail, place):
            ctx["detail_attempts"][ref] = detail
        # Keep an already proven supplier link even when a new data query is needed.
        if (detail.get("match_status", "matched") == "matched" and detail_matches_place(detail, place)
                and detail.get("evidence") and all(e.get("match_status") == "matched" for e in detail["evidence"])):
            ctx["places"][ref] = dict(place, provider_refs=detail["place"].get("provider_refs", {}))
    return ctx
