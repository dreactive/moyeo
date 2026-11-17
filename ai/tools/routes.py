from copy import deepcopy


def observed_route(context, arguments):
    for key in ("from_ref", "to_ref"):
        if arguments[key] not in context["places"]:
            raise ValueError("Route endpoint not observed")
    for observation in context.get("observations", []):
        leg = observation["result"]
        same_time = observation.get("arguments", {}).get("departure_at") == arguments.get("departure_at")
        if same_time and all(leg.get(k) == arguments[k] for k in ("from_ref", "to_ref")):
            return deepcopy(leg)
    raise ValueError("Route leg missing; never substitute zero seconds")
