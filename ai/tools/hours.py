from datetime import datetime, timedelta
import json

from ai.conflicts import conflict


def _closed_days(hours):
    holiday_text = hours.get("holiday_text") or ""
    try:
        raw = json.loads(holiday_text)
    except json.JSONDecodeError:
        return set()
    return set(raw.get("closed_dates", [])) if isinstance(raw, dict) else set()


def _instant(day, clock, tz):
    start = datetime.fromisoformat(day).replace(tzinfo=tz)
    hour, minute = (int(part) for part in clock.split(":"))
    return start + timedelta(hours=hour, minutes=minute)


def validate_hours(visit, details, versions):
    hours = details.get("opening_hours") or {}
    start, end = (datetime.fromisoformat(visit[key]) for key in ("start_at", "end_at"))
    dates = {(start.date() + timedelta(days=offset)).isoformat()
             for offset in range(((end - timedelta(microseconds=1)).date() - start.date()).days + 1)}
    closed = _closed_days(hours)
    if not closed and dates and "휴무" in (hours.get("holiday_text") or ""):
        # Stored fixture/legacy text may contain a date followed by a closure label.
        closed = {day for day in dates if day + " 휴무" in hours["holiday_text"]}
    intervals = sorted((_instant(i["day"], i["start"], start.tzinfo), _instant(i["day"], i["end"], start.tzinfo))
                       for i in hours.get("intervals") or [] if i["day"] in dates)
    if not intervals and not dates & closed:
        return [], [dict(field="opening_hours", item_id=visit["item_id"], place_ref=visit.get("place_ref"), date=visit["date"])]
    cursor = start
    if not dates & closed:
        for opening, closing in intervals:
            if opening <= cursor < closing:
                cursor = closing
            if cursor >= end:
                return [], []
    return [conflict("opening_hours", "방문 시간이 확인된 운영시간과 충돌합니다.", [visit["item_id"]], versions)], []
