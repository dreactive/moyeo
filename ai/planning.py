from datetime import date, datetime, timedelta
from ai.tools.itinerary import schedule_visit
from ai.tools.context import build_tool_context
from ai.tools.routes import route_matches


def resolved_item_visits(context):
    target = None if context.get("current_plan") is None else set(context.get("_new_item_refs", []))
    visits = []
    for item in context["items"]:
        if item.get("kind") != "place" or (target is not None and item["id"] not in target):
            continue
        for observation in reversed(context["observations"]):
            args = observation["arguments"]
            if observation["tool_name"] != "search_places" or args.get("query") != item["title"] or args.get("region") != context["config"]["region"]:
                continue
            places = observation["result"]["places"]
            exact = [p for p in places if p["name"] == item["title"]]
            matches = exact or places
            if len(matches) == 1:
                visits.append(dict(item_id=item["id"], place_ref=matches[0]["id"], date=context["config"]["start_date"],
                                   preferred_start_at=None, stay_minutes=None, selected_menu_ids=[]))
            break
    return visits


def planned_visits(context):
    plan = context.get("current_plan") or {}
    refs = {i["id"]: i.get("place_ref") for i in plan.get("item_snapshots", [])}
    visits = [dict(item_id=v["item_id"], place_ref=refs.get(v["item_id"]) or v["place_ref"],
                 date=d["date"], preferred_start_at=v.get("start_at"),
                 stay_minutes=v.get("stay_minutes"), selected_menu_ids=v.get("selected_menu_ids", []))
            for d in plan.get("days", []) for v in d["visits"]]
    visits.extend(resolved_item_visits(context))
    for q in context.get("questions", []):
        if q["status"] != "answered" or q.get("owner_id") not in (None, q.get("answered_by")):
            continue
        for visit in visits:
            if visit["item_id"] == q["target_ref"]:
                if q["field"] == "visit_duration":
                    visit["stay_minutes"] = q["answer"]["stay_minutes"]
                if q["field"] == "menu_selection":
                    visit["selected_menu_ids"] = [q["answer"]["menu_id"]]
    return visits


def planning_inputs_ready(context):
    context = build_tool_context(context)
    plan = context.get("current_plan")
    expected = ({i["id"] for i in context["items"] if i.get("kind") == "place"} if plan is None else
                set(plan.get("selected_item_ids", [v["item_id"] for d in plan.get("days", []) for v in d["visits"]])))
    expected.update(context.get("_new_item_refs", []))
    visits = planned_visits(context)
    anchors = ("origin", "destination") + (("lodging",) if context["config"]["start_date"] != context["config"]["end_date"] else ())
    if any("anchor:" + name not in context["places"] for name in anchors):
        return False
    if (plan is None and not expected) or not expected <= {v["item_id"] for v in visits} or pending_routes(context):
        return False
    if any(v["place_ref"] not in context["details"] for v in visits):
        return False
    if context.get("_provider_mode") == "live":
        if any(e["mode"] != "live" for v in visits for e in context["details"][v["place_ref"]]["evidence"]):
            return False
        if any(o["result"]["evidence_id"].startswith("fixture:") for o in selected_route_observations(context)):
            return False
    return True


def itinerary_arguments(context):
    return dict(visits=planned_visits(context),
                anchors={k: context["config"].get(k) for k in ("origin", "destination", "lodging")},
                constraints=context["constraints"],
                route_legs=[o["result"] for o in selected_route_observations(context)])




def next_route(context, only_day=None):
    context = build_tool_context(context)
    config, visits = context["config"], planned_visits(context)
    first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
    for offset in range((last - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        if only_day is not None and day != only_day:
            continue
        cursor = datetime.fromisoformat(day + "T" + config.get("day_start_time", "09:00") + ":00+09:00")
        previous = "anchor:origin" if offset == 0 else "anchor:lodging"
        day_visits = [v for v in visits if v["date"] == day]
        destination = "anchor:destination" if day == config["end_date"] else "anchor:lodging"
        for visit in day_visits + [dict(place_ref=destination)]:
            arguments = dict(from_ref=previous, to_ref=visit["place_ref"], departure_at=cursor.isoformat())
            observed = next((o["result"] for o in reversed(context["observations"])
                             if route_matches(o, context, arguments)), None)
            if observed is None:
                return arguments
            if "item_id" in visit:
                cursor = datetime.fromisoformat(schedule_visit(visit, cursor, observed["duration_seconds"])["end_at"])
            previous = visit["place_ref"]
    return None


def pending_routes(context):
    first, last = (date.fromisoformat(context["config"][k]) for k in ("start_date", "end_date"))
    routes = [next_route(context, (first + timedelta(days=n)).isoformat()) for n in range((last - first).days + 1)]
    return [r for r in routes if r is not None]


def selected_route_observations(context):
    context = build_tool_context(context)
    config, visits, selected = context["config"], planned_visits(context), []
    first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
    for offset in range((last - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        cursor = datetime.fromisoformat(day + "T" + config.get("day_start_time", "09:00") + ":00+09:00")
        previous = "anchor:origin" if offset == 0 else "anchor:lodging"
        target = "anchor:destination" if day == config["end_date"] else "anchor:lodging"
        for visit in [v for v in visits if v["date"] == day] + [dict(place_ref=target)]:
            args = dict(from_ref=previous, to_ref=visit["place_ref"], departure_at=cursor.isoformat())
            observed = next((o for o in reversed(context["observations"])
                             if route_matches(o, context, args)), None)
            if observed is None:
                break
            selected.append(observed)
            if "item_id" in visit:
                cursor = datetime.fromisoformat(schedule_visit(visit, cursor, observed["result"]["duration_seconds"])["end_at"])
            previous = visit["place_ref"]
    return selected
