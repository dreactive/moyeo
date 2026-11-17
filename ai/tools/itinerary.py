from datetime import date, datetime, timedelta
from ai.questions import question


def build_itinerary(visits, anchors, constraints, route_legs, config):
    first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
    days = [dict(date=(first + timedelta(days=n)).isoformat(), visits=[], route_legs=[])
            for n in range((last - first).days + 1)]
    questions = []
    for day in days:
        previous = "anchor:origin" if day["date"] == config["start_date"] else "anchor:lodging"
        cursor = datetime.fromisoformat(day["date"] + "T" + config.get("day_start_time", "09:00") + ":00+09:00")
        for visit in [v for v in visits if v["date"] == day["date"]]:
            leg = next((r for r in route_legs if r["from_ref"] == previous and r["to_ref"] == visit["place_ref"]), None)
            if leg is None:
                questions.append(question("constraint_value", visit["item_id"], "자동차 이동 구간을 조회해주세요."))
                break
            scheduled = schedule_visit(visit, cursor, leg["duration_seconds"])
            day["visits"].append(scheduled)
            day["route_legs"].append(leg)
            cursor, previous = datetime.fromisoformat(scheduled["end_at"]), visit["place_ref"]
    return dict(days=days, questions=questions, conflicts=[])


def schedule_visit(visit, cursor, duration_seconds):
    start = cursor + timedelta(seconds=duration_seconds)
    if visit.get("preferred_start_at"):
        start = max(start, datetime.fromisoformat(visit["preferred_start_at"]))
    stay = visit.get("stay_minutes") or 60
    return dict(item_id=visit["item_id"], place_ref=visit["place_ref"], date=visit["date"],
                start_at=start.isoformat(), end_at=(start + timedelta(minutes=stay)).isoformat(),
                stay_minutes=stay, selected_menu_ids=visit.get("selected_menu_ids", []),
                assumptions=[] if visit.get("stay_minutes") else ["기본 체류 60분; 변경 가능"])
