from ai.planning import planned_visits, next_route, itinerary_arguments
from ai.cost_inputs import build_cost_inputs


def tool(name, arguments):
    return dict(action="tool", reason="fixture model decision", tool_name=name, arguments=arguments,
                source_message_ids=[], source_refs=[])


def propose_actions(context):
    visits = planned_visits(context)
    detailed = {o["result"]["place"]["id"] for o in context["observations"] if "place" in o["result"]}
    for visit in visits:
        if visit["place_ref"] not in detailed:
            return [tool("get_place_details", {"place_ref": visit["place_ref"]})]
    route = next_route(context)
    if route:
        return [tool("get_car_route", route)]
    observed = {o["tool_name"] for o in context["observations"]}
    if "build_itinerary" not in observed:
        return [tool("build_itinerary", itinerary_arguments(context))]
    if "calculate_costs" not in observed:
        return [tool("calculate_costs", build_cost_inputs(context)[0])]
    return []
