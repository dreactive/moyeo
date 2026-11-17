import math
from ai.cost_inputs import build_cost_inputs
from ai.planning import itinerary_arguments, planning_inputs_ready

PARAMETERS = {
    "search_places": {"query": str, "region": str, "category": (str, type(None))},
    "get_place_details": {"place_ref": str},
    "get_car_route": {"from_ref": str, "to_ref": str, "departure_at": (str, type(None))},
    "build_itinerary": {"visits": list, "anchors": dict, "constraints": list, "route_legs": list},
    "calculate_costs": {"lines": list, "member_ids": list, "budget_by_user": dict},
}


def validate_arguments(name, arguments, context):
    schema = PARAMETERS.get(name)
    if schema is None or set(arguments) != set(schema):
        raise ValueError("Unregistered tool or missing/unexpected arguments")
    if any(not isinstance(arguments[k], t) for k, t in schema.items()):
        raise ValueError("Invalid argument type")
    if name == "search_places" and (not arguments["query"].strip() or arguments["region"] != context["config"].get("region")):
        raise ValueError("Search needs a nonempty query in the configured region")
    for key in ("place_ref", "from_ref", "to_ref"):
        if key in arguments and arguments[key] not in context["places"]:
            raise ValueError("Unobserved place reference")
    for line in arguments.get("lines", []):
        quantity = line.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be finite and positive")
    if name == "calculate_costs":
        if "members" not in context or arguments != build_cost_inputs(context)[0]:
            raise ValueError("Cost arguments differ from observed prices and user inputs")
    if name == "build_itinerary" and arguments != itinerary_arguments(context):
        raise ValueError("Itinerary arguments differ from task facts and observed route seconds")
    if name in ("build_itinerary", "calculate_costs") and not planning_inputs_ready(context):
        raise ValueError("Resolve selected items, details and actual route departures before calculations")
