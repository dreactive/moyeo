import math

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
    for key in ("place_ref", "from_ref", "to_ref"):
        if key in arguments and arguments[key] not in context["places"]:
            raise ValueError("Unobserved place reference")
    for line in arguments.get("lines", []):
        quantity = line.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("Quantity must be finite and positive")
