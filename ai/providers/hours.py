from datetime import date
import re
import json


def closed_dates(hours, days):
    closed = []
    for day in days:
        weekday = "월화수목금토일"[date.fromisoformat(day).weekday()]
        for section in hours or []:
            explicit = json.dumps([section.get("comingRegularClosedDays"),
                                   section.get("comingIrregularClosedDays")], ensure_ascii=False).replace(".", "-")
            spans = section.get("schedule") or []
            weekly = any(s.get("day") in (weekday, weekday + "요일", "매일") and
                         "휴무" in (s.get("description") or "") for s in spans)
            if weekly or day in explicit:
                closed.append(day)
    return sorted(set(closed))


def expand_hours(hours, days):
    intervals = []
    for day in days:
        weekday = "월화수목금토일"[date.fromisoformat(day).weekday()]
        for section in hours or []:
            for span in section.get("schedule") or []:
                if span.get("day") not in ("매일", weekday, weekday + "요일", day):
                    continue
                if not all(re.fullmatch(r"\d{2}:\d{2}", span.get(k) or "") for k in ("start", "end")):
                    continue
                if span["start"] < span["end"]:
                    cursor = span["start"]
                    for pause in sorted(span.get("breakHours") or [], key=lambda p: p["start"]):
                        if cursor < pause["start"] < span["end"]:
                            intervals.append(dict(day=day, start=cursor, end=pause["start"]))
                        cursor = max(cursor, pause["end"])
                    if cursor < span["end"]:
                        intervals.append(dict(day=day, start=cursor, end=span["end"]))
    return intervals
