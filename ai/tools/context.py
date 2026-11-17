from copy import deepcopy


def build_tool_context(context):
    ctx = deepcopy(context)
    ctx["places"], ctx["details"] = {}, {}
    for name in ("origin", "destination", "lodging"):
        if ctx["config"].get(name):
            ctx["places"]["anchor:" + name] = ctx["config"][name]
    for observation in ctx.get("observations", []):
        result = observation["result"]
        for place in result.get("places", []) + ([result["place"]] if "place" in result else []):
            ctx["places"][place["id"]] = place
        if "place" in result:
            ctx["details"][result["place"]["id"]] = result
    return ctx
