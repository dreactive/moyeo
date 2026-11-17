from ai.questions import question
from ai.conflicts import conflict


def validate_hours(visit, details, versions):
    hours = details.get("opening_hours") or {}
    intervals = [i for i in hours.get("intervals") or [] if i["day"] == visit["date"]]
    closed = visit["date"] in (hours.get("holiday_text") or "")
    if not intervals and not closed:
        return [], [question("constraint_value", visit["item_id"], "방문일 영업시간을 확인해주세요.")]
    fits = any(i["start"] <= visit["start_at"][11:16] and i["end"] >= visit["end_at"][11:16]
               for i in intervals)
    if closed or not fits:
        return [conflict("opening_hours", "방문 시간이 확인된 운영시간과 충돌합니다.",
                         [visit["item_id"]], versions)], []
    return [], []
