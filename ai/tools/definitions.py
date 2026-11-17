TOOL_DEFINITIONS = [
    {"name": "search_places", "description": "Search places; returns PlaceRef IDs", "parameters": {
        "query": "string", "region": "string", "category": "string|null"}},
    {"name": "get_place_details", "description": "Observe same-branch menus and opening hours", "parameters": {"place_ref": "string"}},
    {"name": "get_car_route", "description": "Observe driving route in meters and seconds", "parameters": {
        "from_ref": "string", "to_ref": "string", "departure_at": "ISO8601|null"}},
    {"name": "build_itinerary", "description": "Code calculates schedule using provided canonical inputs", "parameters": {
        "visits": "array", "anchors": "object", "constraints": "array", "route_legs": "array"}},
    {"name": "calculate_costs", "description": "Code calculates exact KRW shares from canonical inputs", "parameters": {
        "lines": "array", "member_ids": "array", "budget_by_user": "object"}},
]
