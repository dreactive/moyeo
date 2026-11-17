from datetime import date, datetime, timedelta
from ai.questions import question


def build_itinerary(visits, anchors, constraints, route_legs, config):
    first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
    days = [dict(date=(first + timedelta(days=n)).isoformat(), visits=[], route_legs=[])
            for n in range((last - first).days + 1)]
    questions = [question("constraint_value", v["item_id"], "자동차 이동 구간을 조회해주세요.",
                          related_item_ids=[v["item_id"]]) for v in visits]
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
