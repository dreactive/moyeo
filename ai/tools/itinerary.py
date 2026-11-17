from datetime import date, datetime, timedelta


def schedule_visit(visit, cursor, duration_seconds):
    start = cursor + timedelta(seconds=duration_seconds)
    if visit.get("preferred_start_at"):
        start = max(start, datetime.fromisoformat(visit["preferred_start_at"]))
    stay = visit.get("stay_minutes") or 60
    return dict(item_id=visit["item_id"], place_ref=visit["place_ref"], date=visit["date"],
                start_at=start.isoformat(), end_at=(start + timedelta(minutes=stay)).isoformat(),
                stay_minutes=stay, selected_menu_ids=visit.get("selected_menu_ids", []),
                assumptions=[] if visit.get("stay_minutes") else ["기본 체류 60분; 변경 가능"])
