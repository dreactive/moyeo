"""Narrow, source-preserving assistance; never a claim of model extraction quality."""
import re
from ai.questions import question
from ai.extraction import validate_extraction


def explicit_items(task):
    proposals = []
    existing = [i["title"].split()[-1] for i in task["items"]]
    for message in task["recent_messages"][-20:]:
        text = message["text"].strip().rstrip(".!?")
        match = re.fullmatch(r"(.+?)\s*(?:가자|어때|좋아|찬성)", text)
        if not match or any(w in text for w in ("다들", "모두", "말고", "대신")):
            continue
        title = re.sub(r"^(나는|난|우리|저는)\s+", "", match[1]).strip()
        if any(t in title for t in existing) or not any(w in title for w in (
            "식당", "공원", "카페", "박물관", "오동도", "케이블카", "아쿠아플라넷", "루지", "게장", "해장국", "전망대", "해수욕장")):
            continue
        proposals.append(dict(client_ref="client:" + message["id"], existing_item_id=None, kind="place",
                              title=title, source_message_ids=[message["id"]]))
        existing.append(title)
    return proposals


def assist_extraction(raw, task):
    output = validate_extraction(raw, task)
    for proposal in explicit_items(task):
        if not any(i["title"] == proposal["title"] for i in output["item_proposals"]):
            output["item_proposals"].append(proposal)
    for proposal in explicit_constraints(task):
        family = ("budget", "budget_krw") if proposal["key"] in ("budget", "budget_krw") else (proposal["key"],)
        output["constraint_proposals"] = [c for c in output["constraint_proposals"]
            if not (c["owner_id"] == proposal["owner_id"] and c["key"] in family
                    and c["source_message_ids"] == proposal["source_message_ids"])]
        output["constraint_proposals"].append(proposal)
    items = task["items"] + [dict(i, id=i["client_ref"], item_version=1) for i in output["item_proposals"]]
    claims, questions = explicit_support(task, items)
    grounded = validate_extraction(dict(item_proposals=output["item_proposals"], support_observations=claims), task)
    for key in ("support_observations", "questions"):
        for value in grounded[key] + (questions if key == "questions" else []):
            if value not in output[key]:
                output[key].append(value)
    return output


def explicit_support(task, items):
    claims, questions = [], []
    for message in task["recent_messages"][-20:]:
        text = message["text"]
        if any(w in text for w in ("다들", "모두", "했대")) or not any(w in text for w in ("가자", "좋아", "찬성", "반대", "철회", "싫어")):
            continue
        stance = "withdraw" if "철회" in text else "oppose" if "반대" in text or "싫어" in text else "support"
        matches = [i for i in items if i["title"].split()[-1] in text]
        if len(matches) == 1:
            item = matches[0]
            claims.append(dict(item_id=item["id"], item_version=item["item_version"], author_id=message["author_id"],
                               stance=stance, source_message_id=message["id"]))
        else:
            missing = question("support_target", None, "어느 항목에 대한 의견인가요?", message["author_id"])
            missing["id"] = f"question:support_target:{stance}:" + message["id"]
            questions.append(missing)
    return claims, questions


def explicit_constraints(task):
    proposals = []
    users = {m["user_id"] for m in task["members"]}
    for message in task["recent_messages"][-20:]:
        if message["author_id"] not in users or "전체" in message["text"]:
            continue
        match = re.search(r"예산.{0,10}?(\d+)\s*만\s*원", message["text"])
        if match:
            old = next((c for c in task["constraints"] if c["owner_id"] == message["author_id"]
                        and c["key"] in ("budget", "budget_krw") and c.get("status") != "superseded"), None)
            proposals.append(dict(owner_id=message["author_id"], key=old["key"] if old else "budget_krw",
                value=int(match[1]) * 10000, kind="hard", source_message_ids=[message["id"]],
                replaces_constraint_id=old["id"] if old else None))
        deadline = re.search(r"(\d{1,2})(?::(\d{2}))?\s*시?\s*까지", message["text"])
        if deadline and any(w in message["text"] for w in ("도착", "귀가", "돌아")):
            hour, minute = int(deadline[1]), int(deadline[2] or 0)
            if hour < 24 and minute < 60:
                old = next((c for c in task["constraints"] if c["owner_id"] == message["author_id"]
                            and c["key"] == "return_by" and c.get("status") != "superseded"), None)
                proposals.append(dict(owner_id=message["author_id"], key="return_by", value=f"{hour:02}:{minute:02}",
                    kind="hard", source_message_ids=[message["id"]], replaces_constraint_id=old["id"] if old else None))
    return proposals
