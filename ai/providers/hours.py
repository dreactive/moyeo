from datetime import date, timedelta
import json
import re


def _applies(span, day):
    weekday = "월화수목금토일"[day.weekday()]
    return span.get("day") in (weekday, weekday + "요일", "매일", day.isoformat())


def _closure(description):
    text = re.sub(r"휴무(?:일)?(?:가|이|은|는)?\s*[:：]?\s*(?:없[가-힣]*|아님)", "", description or "")
    return "휴무" in text


def closed_dates(hours, days):
    closed = set()
    for section in hours or []:
        raw_closures = json.dumps([section.get("comingRegularClosedDays"), section.get("comingIrregularClosedDays")],
                                  ensure_ascii=False).replace(".", "-")
        for day in days:
            if day in raw_closures or any(_applies(span, date.fromisoformat(day)) and _closure(span.get("description"))
                                          for span in section.get("schedule") or []):
                closed.add(day)
    return sorted(closed)


def _minute(text):
    if not isinstance(text, str) or not re.fullmatch(r"\d{2}:[0-5]\d", text):
        return None
    hour, minute = (int(part) for part in text.split(":"))
    return hour * 60 + minute if hour < 48 else None


def _clock(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


def _segments(span):
    start, end = (_minute(span.get(k)) for k in ("start", "end"))
    if start is None or end is None or start >= 1440 or start == end:
        return []
    if end < start:
        end += 1440
    if end - start > 1440:
        return []
    pauses = []
    for pause in span.get("breakHours") or []:
        left, right = (_minute(pause.get(k)) for k in ("start", "end"))
        if left is None or right is None or left == right:
            continue
        if right < left:
            right += 1440
        pauses.append((left, right))
        if end > 1440 and left < 1440:
            pauses.append((left + 1440, right + 1440))
    cursor, segments = start, []
    for left, right in sorted(pauses):
        if left >= end or right <= cursor:
            continue
        if left > cursor:
            segments.append((cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        segments.append((cursor, end))
    return segments


def expand_hours(hours, days):
    wanted = {date.fromisoformat(day) for day in days}
    one_day = timedelta(days=1)
    source_days = wanted | {day - one_day for day in wanted}
    closed = set(closed_dates(hours, [(day + offset * one_day).isoformat()
                                    for day in source_days for offset in (0, 1)]))
    intervals = set()
    for day in source_days:
        if day.isoformat() in closed:
            continue
        tomorrow = (day + one_day).isoformat()
        for section in hours or []:
            for span in section.get("schedule") or []:
                if not _applies(span, day):
                    continue
                for start, end in _segments(span):
                    if day in wanted and start < 1440:
                        intervals.add((day.isoformat(), start, min(end, 1440)))
                    if end > 1440 and tomorrow not in closed:
                        intervals.add((tomorrow, max(0, start - 1440), end - 1440))
    return [dict(day=day, start=_clock(start), end=_clock(end)) for day, start, end in sorted(intervals)]
