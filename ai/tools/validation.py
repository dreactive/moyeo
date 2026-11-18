import json
import math

from ai.cost_inputs import build_cost_inputs, cost_inputs_ready
from ai.planning import itinerary_arguments, itinerary_inputs_ready
from ai.tools.routes import valid_route_request

PARAMETERS = {
    "search_places": {"query": str, "region": str, "category": (str, type(None))},
    "get_place_details": {"place_ref": str},
    "get_car_route": {"from_ref": str, "to_ref": str, "departure_at": (str, type(None))},
    "build_itinerary": {"visits": list, "anchors": dict, "constraints": list, "route_legs": list, "trip_schedule": dict},
    "calculate_costs": {"lines": list, "member_ids": list, "budget_by_user": dict},
}


def same_arguments(arguments, canonical):
    return json.dumps(arguments, sort_keys=True) == json.dumps(canonical, sort_keys=True)


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
    if name == "get_car_route" and not valid_route_request(context, arguments):
        raise ValueError("A driving route needs observed coordinates and an applicable departure time")
    for line in arguments.get("lines", []):
        quantity = line.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be finite and positive")
    if name == "calculate_costs":
        if "members" not in context or not same_arguments(arguments, build_cost_inputs(context)[0]):
            raise ValueError("Cost arguments differ from observed prices and user inputs")
        if not cost_inputs_ready(context, arguments):
            raise ValueError("Cost calculation needs an applicable cost scope, members and budgets")
    if name == "build_itinerary":
        if not same_arguments(arguments, itinerary_arguments(context)):
            raise ValueError("Itinerary arguments differ from task facts and observed route seconds")
        if not itinerary_inputs_ready(context):
            raise ValueError("Itinerary needs a schedulable visit with an observed route")
