from datetime import date, datetime, timedelta
from hashlib import sha256
import json

from ai.tools.context import build_tool_context
from ai.tools.hours import validate_hours
from ai.tools.itinerary import schedule_visit
from ai.tools.routes import route_matches


def active_place_item(item):
    if item.get("kind") != "place" or item.get("active") is False:
        return False
    if item.get("state") in ("inactive", "opposed", "rejected", "excluded", "removed", "archived", "deleted", "dropped"):
        return False
    return not (item.get("opponent_ids") and not item.get("supporter_ids"))


def selected_place_items(context):
    active = {i["id"]: i for i in context["items"] if active_place_item(i)}
    plan = context.get("current_plan")
    if plan is None:
        return list(active.values())
    selected = plan.get("selected_item_ids")
    if selected is None:
        selected = [v["item_id"] for d in plan.get("days", []) for v in d["visits"]]
        selected += [i["id"] for i in plan.get("item_snapshots", [])]
    return [active[ref] for ref in dict.fromkeys([*selected, *context.get("_new_item_refs", [])]) if ref in active]


def _search_ref(context, item):
    for observation in reversed(context["observations"]):
        args = observation["arguments"]
        if (observation["tool_name"] != "search_places" or args.get("query") != item["title"]
                or args.get("region") != context["config"].get("region")):
            continue
        places = observation["result"]["places"]
        matches = [p for p in places if p["name"] == item["title"]] or places
        return matches[0]["id"] if len(matches) == 1 else None
    return None


def _item_refs(plan):
    refs = {i["id"]: i.get("place_ref") for i in plan.get("item_snapshots", []) if i.get("place_ref")}
    for item in plan.get("unplaced_items", []):
        if item.get("place_ref"):
            refs.setdefault(item["item_id"], item["place_ref"])
    return refs


def _recovered_visits(context, items, refs, scheduled_ids=()):
    plan = context.get("current_plan") or {}
    dates = {gap["item_id"]: gap["date"] for gap in plan.get("missing_observations", [])
             if gap.get("field") == "route" and gap.get("item_id") and gap.get("date")}
    start_date = context["config"].get("start_date")
    for item in items:
        if item["id"] in scheduled_ids:
            continue
        ref = refs.get(item["id"]) or item.get("place_ref") or _search_ref(context, item)
        if ref:
            yield dict(item_id=item["id"], place_ref=ref, date=dates.get(item["id"], start_date),
                       preferred_start_at=None, stay_minutes=None, selected_menu_ids=[])


def resolved_item_visits(context):
    plan = context.get("current_plan") or {}
    scheduled = {v["item_id"] for day in plan.get("days", []) for v in day["visits"]}
    return list(_recovered_visits(context, selected_place_items(context), _item_refs(plan), scheduled))


def planned_visits(context):
    plan = context.get("current_plan") or {}
    items = selected_place_items(context)
    selected = {i["id"] for i in items}
    refs = _item_refs(plan)
    visits = [dict(item_id=v["item_id"], place_ref=refs.get(v["item_id"]) or v["place_ref"],
                   date=d["date"], preferred_start_at=v.get("start_at"),
                   stay_minutes=v.get("stay_minutes"), selected_menu_ids=v.get("selected_menu_ids", []))
              for d in plan.get("days", []) for v in d["visits"] if v["item_id"] in selected]
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


def missing_visit_locations(context, visits):
    visible = {v["item_id"]: v["place_ref"] for v in visits}
    return [dict(item_id=i["id"], place_ref=visible.get(i["id"]), reason="unresolved_place")
            for i in selected_place_items(context) if visible.get(i["id"]) not in context["places"]]


def route_inputs(context):
    """Walk each day's actual route chain, keeping unknown downstream departure times unset."""
    context = build_tool_context(context)
    config = context["config"]
    visits = [visit for visit in planned_visits(context) if visit["place_ref"] in context["places"]]
    try:
        first, last = (date.fromisoformat(config.get(k)) for k in ("start_date", "end_date"))
    except (TypeError, ValueError):
        return
    for offset in range((last - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        cursor = datetime.fromisoformat(day + "T" + config.get("day_start_time", "09:00") + ":00+09:00")
        previous = "anchor:origin" if offset == 0 else "anchor:lodging"
        destination = "anchor:destination" if day == config["end_date"] else "anchor:lodging"
        for visit in (v for v in [*visits, dict(place_ref=destination, date=day)] if v["date"] == day):
            args = dict(from_ref=previous, to_ref=visit["place_ref"], departure_at=cursor.isoformat() if cursor else None)
            observed = next((o for o in reversed(context["observations"]) if route_matches(o, context, args)), None) if cursor else None
            yield day, args, visit if "item_id" in visit else None, observed
            if observed is None:
                cursor = None
            elif "item_id" in visit:
                cursor = datetime.fromisoformat(schedule_visit(visit, cursor, observed["result"]["duration_seconds"])["end_at"])
            previous = visit["place_ref"]


def next_route(context, only_day=None):
    return next((args for day, args, _, observed in route_inputs(context)
                 if observed is None and args["departure_at"] and (only_day is None or only_day == day)), None)


def pending_routes(context):
    return [args for _, args, _, observed in route_inputs(context) if observed is None and args["departure_at"]]


def selected_route_observations(context):
    return [observed for _, _, _, observed in route_inputs(context) if observed is not None]


def itinerary_arguments(context):
    context = build_tool_context(context)
    config, visits = context["config"], planned_visits(context)
    selected = {i["id"]: i for i in selected_place_items(context)}
    represented = {v["item_id"] for v in visits}
    visits.extend(dict(item_id=item_id, place_ref=None, date=config.get("start_date"),
                       preferred_start_at=None, stay_minutes=None, selected_menu_ids=[])
                  for item_id in selected if item_id not in represented)
    for visit in visits:
        ref = visit["place_ref"]
        if ref not in context["places"]:
            visit["place_ref"] = None
        hours = context["details"].get(ref, {}).get("opening_hours")
        fingerprint = sha256(json.dumps(hours, sort_keys=True).encode()).hexdigest()[:20] if hours else None
        visit["input_basis"] = dict(item_version=selected[visit["item_id"]].get("item_version"),
                                    opening_hours_evidence_id=(hours or {}).get("evidence_id"),
                                    opening_hours_fingerprint=fingerprint)
    return dict(visits=visits,
                trip_schedule=dict(start_date=config.get("start_date"), end_date=config.get("end_date"),
                                   day_start_time=config.get("day_start_time", "09:00"),
                                   day_end_time=config.get("day_end_time", "18:00")),
                anchors={k: config.get(k) for k in ("origin", "destination", "lodging")},
                constraints=context["constraints"],
                route_legs=[dict(o["result"], departure_at=o["arguments"]["departure_at"])
                            for o in selected_route_observations(context)])


def itinerary_inputs_ready(context):
    routes = list(route_inputs(context))
    return any(visit and observed for _, _, visit, observed in routes) or bool(
        routes and context.get("current_plan") is not None and not selected_place_items(context)
        and all(observed for _, _, _, observed in routes))


def planning_inputs_ready(context):
    """Require every selected visit, observed detail, and real route for final readiness."""
    context = build_tool_context(context)
    config, visits = context["config"], planned_visits(context)
    routes = list(route_inputs(context))
    if not routes:
        return False
    anchors = ("origin", "destination") + (("lodging",) if config["start_date"] != config["end_date"] else ())
    if any("anchor:" + name not in context["places"] for name in anchors):
        return False
    if context.get("current_plan") is None and not selected_place_items(context):
        return False
    if missing_visit_locations(context, visits) or any(not v["date"] or not config["start_date"] <= v["date"] <= config["end_date"]
                                                       for v in visits):
        return False
    for _, args, visit, observed in routes:
        if observed is None or not observed["result"].get("evidence_id"):
            return False
        if visit:
            ref = visit["place_ref"]
            if ref not in context["details"]:
                return False
            scheduled = schedule_visit(visit, datetime.fromisoformat(args["departure_at"]), observed["result"]["duration_seconds"])
            if validate_hours(scheduled, context["details"][ref], context.get("base_versions", {}))[1]:
                return False
    return True
