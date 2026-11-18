from datetime import date, datetime, timedelta
from ai.questions import question
from ai.conflicts import conflict
from ai.tools.hours import validate_hours


def matching_leg(legs, from_ref, to_ref, consume=False, departure_at=None):
    for index, leg in enumerate(legs):
        if (leg["from_ref"] == from_ref and leg["to_ref"] == to_ref
                and ("departure_at" not in leg or leg["departure_at"] == departure_at)):
            return legs.pop(index) if consume else leg
    return None


def finish_day(day, destination, route_legs, end_time, versions, origin=None, start_time="09:00", consume=False):
    if not day["visits"] and origin is None:
        return [], []
    visit = day["visits"][-1] if day["visits"] else dict(place_ref=origin,
             end_at=day["date"] + "T" + start_time + ":00+09:00")
    leg = matching_leg(route_legs, visit["place_ref"], destination, consume, visit["end_at"])
    if leg is None:
        return [], [dict(field="route", from_ref=visit["place_ref"], to_ref=destination,
                         date=day["date"], departure_at=visit["end_at"])]
    day["route_legs"].append(leg)
    arrival = datetime.fromisoformat(visit["end_at"]) + timedelta(seconds=leg["duration_seconds"])
    deadline = datetime.fromisoformat(day["date"] + "T" + end_time + ":00+09:00")
    conflicts = [conflict("time", "도착 시간이 활동/귀가 제한을 넘습니다.",
                         [visit["item_id"]] if "item_id" in visit else [], versions)] if arrival > deadline else []
    return conflicts, []


def build_itinerary(visits, anchors, constraints, route_legs, config, trip_schedule=None):
    config = dict(config, **trip_schedule) if trip_schedule else config
    first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
    available = list(route_legs)
    days = [dict(date=(first + timedelta(days=n)).isoformat(), visits=[], route_legs=[])
            for n in range((last - first).days + 1)]
    questions, conflicts = [], []
    unplaced = {v["item_id"]: dict(item_id=v["item_id"], place_ref=None, reason="unresolved_place")
                for v in visits if v["place_ref"] is None}
    missing = [dict(field="location", item_id=i["item_id"], place_ref=i["place_ref"]) for i in unplaced.values()]
    for visit in visits:
        if not visit["date"] or not config["start_date"] <= visit["date"] <= config["end_date"]:
            unplaced.setdefault(visit["item_id"], dict(item_id=visit["item_id"], place_ref=visit["place_ref"],
                                                      reason="outside_trip_dates"))
    for day in days:
        previous = "anchor:origin" if day["date"] == config["start_date"] else "anchor:lodging"
        cursor = datetime.fromisoformat(day["date"] + "T" + config.get("day_start_time", "09:00") + ":00+09:00")
        for visit in [v for v in visits if v["date"] == day["date"] and v["place_ref"] is not None]:
            departure_at = cursor.isoformat() if cursor else None
            leg = matching_leg(available, previous, visit["place_ref"], True, departure_at) if cursor else None
            if leg is None:
                unplaced.setdefault(visit["item_id"], dict(item_id=visit["item_id"], place_ref=visit["place_ref"],
                                                          reason="missing_route"))
                missing.append(dict(field="route", item_id=visit["item_id"], from_ref=previous,
                                    to_ref=visit["place_ref"], date=day["date"], departure_at=departure_at))
                cursor, previous = None, visit["place_ref"]
                continue
            scheduled = schedule_visit(visit, cursor, leg["duration_seconds"])
            day["visits"].append(scheduled)
            day["route_legs"].append(leg)
            cursor, previous = datetime.fromisoformat(scheduled["end_at"]), visit["place_ref"]
        destination = "anchor:destination" if day["date"] == config["end_date"] else "anchor:lodging"
        if cursor is None:
            missing.append(dict(field="route", from_ref=previous, to_ref=destination,
                                date=day["date"], departure_at=None))
            continue
        limits = [config.get("day_end_time", "18:00")]
        if day["date"] == config["end_date"]:
            limits += [c["value"] for c in constraints if c["key"] == "return_by"
                       and c["kind"] == "hard" and c["status"] == "confirmed"]
        found, gaps = finish_day(day, destination, available, min(limits), config.get("_base_versions", {}),
                                 previous, config.get("day_start_time", "09:00"), True)
        conflicts.extend(found)
        missing.extend(gaps)
    for key in ("origin", "destination") + (("lodging",) if first != last else ()):
        if anchors.get(key) is None:
            questions.append(question(key, "anchor:" + key, "거점 좌표를 입력해주세요."))
    for day in days:
        for visit in day["visits"]:
            found, gaps = validate_hours(visit, config.get("_details", {}).get(visit["place_ref"], {}),
                                          config.get("_base_versions", {}))
            conflicts.extend(found)
            missing.extend(gaps)
    return dict(days=days, questions=questions, conflicts=conflicts, unplaced_items=list(unplaced.values()),
                missing_observations=missing)


def schedule_visit(visit, cursor, duration_seconds):
    start = cursor + timedelta(seconds=duration_seconds)
    if visit.get("preferred_start_at"):
        start = max(start, datetime.fromisoformat(visit["preferred_start_at"]))
    stay = visit.get("stay_minutes") or 60
    return dict(item_id=visit["item_id"], place_ref=visit["place_ref"], date=visit["date"],
                start_at=start.isoformat(), end_at=(start + timedelta(minutes=stay)).isoformat(),
                stay_minutes=stay, selected_menu_ids=visit.get("selected_menu_ids", []),
                assumptions=[] if visit.get("stay_minutes") else ["기본 체류 60분; 변경 가능"])
