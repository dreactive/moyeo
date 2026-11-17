from ai.planning import planned_visits


def tool(name, arguments):
    return dict(action="tool", reason="fixture model decision", tool_name=name, arguments=arguments,
                source_message_ids=[], source_refs=[])


def propose_actions(context):
    visits = planned_visits(context)
    detailed = {o["result"]["place"]["id"] for o in context["observations"] if "place" in o["result"]}
    for visit in visits:
        if visit["place_ref"] not in detailed:
            return [tool("get_place_details", {"place_ref": visit["place_ref"]})]
    if visits:
        return [tool("get_car_route", dict(from_ref="anchor:origin", to_ref=visits[0]["place_ref"],
                     departure_at=context["config"]["start_date"] + "T09:00:00+09:00"))]
    return []
