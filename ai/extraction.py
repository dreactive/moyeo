"""Validate provenance before accepting model-generated proposals."""
from ai.questions import question
from ai.condition_grounding import condition_value


def validate_support(claim, message, item):
    if not message or not item or message["author_id"] != claim.get("author_id"):
        return None, None
    text = message["text"]
    if claim.get("item_version") != item["item_version"] or any(w in text for w in ("다들", "모두", "했대")):
        return None, None
    stance = "withdraw" if "철회" in text else "oppose" if "반대" in text or "싫어" in text else "support"
    explicit = any(w in text for w in ("가자", "좋아", "찬성", "철회", "반대", "싫어"))
    if not explicit or claim.get("stance") not in (stance, "unclear"):
        return None, None
    if item["title"].split()[-1] not in text:
        missing = question("support_target", None, "어느 항목에 대한 의견인가요?", claim["author_id"])
        missing["id"] = f"question:support_target:{stance}:" + message["id"]
        return None, missing
    return (claim, None) if explicit and claim.get("stance") == stance else (None, None)


def validate_extraction(output, task):
    messages = {m["id"]: m for m in task["recent_messages"][-20:]}
    constraints = {c["id"]: c for c in task["constraints"]}
    accepted = dict(constraint_proposals=[], item_proposals=[], support_observations=[], questions=[])
    for proposal in output.get("constraint_proposals", []):
        sources = proposal.get("source_message_ids", [])
        if not sources or any(m not in messages or messages[m]["author_id"] != proposal.get("owner_id") for m in sources):
            continue
        if not any(condition_value(proposal.get("key"), messages[m]["text"]) == proposal.get("value") and type(condition_value(proposal.get("key"), messages[m]["text"])) is type(proposal.get("value")) for m in sources):
            continue
        old = constraints.get(proposal.get("replaces_constraint_id"))
        if proposal.get("replaces_constraint_id") and (not old or old["owner_id"] != proposal["owner_id"] or old["key"] != proposal["key"]):
            continue
        accepted["constraint_proposals"].append(proposal)
    for proposal in output.get("item_proposals", []):
        sources = proposal.get("source_message_ids", [])
        ref = proposal.get("client_ref")
        if (not ref or not sources or any(m not in messages for m in sources)
                or not any(proposal.get("title", "") and proposal["title"] in messages[m]["text"] for m in sources)):
            continue
        existing = proposal.get("existing_item_id")
        if existing and existing not in {i["id"] for i in task["items"]}:
            continue
        if ref not in {i["client_ref"] for i in accepted["item_proposals"]}:
            accepted["item_proposals"].append(proposal)
    items = {i["id"]: i for i in task["items"]}
    items.update({i["client_ref"]: dict(i, item_version=1) for i in accepted["item_proposals"]})
    for claim in output.get("support_observations", []):
        valid, missing = validate_support(claim, messages.get(claim.get("source_message_id")), items.get(claim.get("item_id")))
        if valid and valid not in accepted["support_observations"]:
            accepted["support_observations"].append(valid)
        if missing and missing not in accepted["questions"]:
            accepted["questions"].append(missing)
    return accepted
