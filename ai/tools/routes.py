from copy import deepcopy
from ai.providers.kakao import route_evidence_id


def route_matches(observation, context, arguments):
    if observation["tool_name"] != "get_car_route" or observation["arguments"] != arguments:
        return False
    evidence = observation["result"].get("evidence_id", "")
    if evidence.startswith("kakao:route:"):
        return evidence == route_evidence_id(context["places"], arguments)
    return True


def observed_route(context, arguments):
    for key in ("from_ref", "to_ref"):
        if arguments[key] not in context["places"]:
            raise ValueError("Route endpoint not observed")
    for observation in reversed(context.get("observations", [])):
        leg = observation["result"]
        if route_matches(observation, context, arguments) and all(leg.get(k) == arguments[k] for k in ("from_ref", "to_ref")):
            return deepcopy(leg)
    raise ValueError("Route leg missing; never substitute zero seconds")
