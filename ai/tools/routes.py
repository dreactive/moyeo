from copy import deepcopy


def observed_route(context, arguments):
    for key in ("from_ref", "to_ref"):
        if arguments[key] not in context["places"]:
            raise ValueError("Route endpoint not observed")
    for observation in context.get("observations", []):
        leg = observation["result"]
        if all(leg.get(k) == arguments[k] for k in ("from_ref", "to_ref")):
            return deepcopy(leg)
    raise ValueError("Route leg missing; never substitute zero seconds")
