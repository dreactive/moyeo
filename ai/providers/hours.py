from datetime import date
import re


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
                    intervals.append(dict(day=day, start=span["start"], end=span["end"]))
    return intervals
