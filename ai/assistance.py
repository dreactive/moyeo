"""Narrow, source-preserving assistance; never a claim of model extraction quality."""
import re


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
    return proposals
