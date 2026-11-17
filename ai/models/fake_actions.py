from ai.planning import planned_visits, next_route, itinerary_arguments
from ai.cost_inputs import build_cost_inputs


def tool(name, arguments):
    return dict(action="tool", reason="fixture model decision", tool_name=name, arguments=arguments,
                source_message_ids=[], source_refs=[])


def propose_actions(context):
    from ai.candidates import grounded_options
    return grounded_options(context)
