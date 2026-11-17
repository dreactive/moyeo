def planned_visits(context):
    plan = context.get("current_plan") or {}
    refs = {i["id"]: i.get("place_ref") for i in plan.get("item_snapshots", [])}
    return [dict(item_id=v["item_id"], place_ref=refs.get(v["item_id"]) or v["place_ref"],
                 date=d["date"], preferred_start_at=v.get("start_at"),
                 stay_minutes=v.get("stay_minutes"), selected_menu_ids=v.get("selected_menu_ids", []))
            for d in plan.get("days", []) for v in d["visits"]]


def itinerary_arguments(context):
    return dict(visits=planned_visits(context),
                anchors={k: context["config"].get(k) for k in ("origin", "destination", "lodging")},
                constraints=context["constraints"],
                route_legs=[o["result"] for o in context["observations"] if o["tool_name"] == "get_car_route"])
from datetime import date, datetime, timedelta
from ai.tools.itinerary import schedule_visit




def next_route(context):
    config, visits = context["config"], planned_visits(context)
    first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
    for offset in range((last - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        cursor = datetime.fromisoformat(day + "T" + config.get("day_start_time", "09:00") + ":00+09:00")
        previous = "anchor:origin" if offset == 0 else "anchor:lodging"
        day_visits = [v for v in visits if v["date"] == day]
        destination = "anchor:destination" if day == config["end_date"] else "anchor:lodging"
        for visit in day_visits + [dict(place_ref=destination)]:
            arguments = dict(from_ref=previous, to_ref=visit["place_ref"], departure_at=cursor.isoformat())
            observed = next((o["result"] for o in context["observations"]
                             if o["tool_name"] == "get_car_route" and o["arguments"] == arguments), None)
            if observed is None:
                return arguments
            if "item_id" in visit:
                cursor = datetime.fromisoformat(schedule_visit(visit, cursor, observed["duration_seconds"])["end_at"])
            previous = visit["place_ref"]
    return None
