"""Validate provenance before accepting model-generated proposals."""


def validate_extraction(output, task):
    messages = {m["id"]: m for m in task["recent_messages"][-20:]}
    constraints = {c["id"]: c for c in task["constraints"]}
    accepted = dict(constraint_proposals=[], item_proposals=[], support_observations=[], questions=[])
    for proposal in output.get("constraint_proposals", []):
        sources = proposal.get("source_message_ids", [])
        if not sources or any(m not in messages or messages[m]["author_id"] != proposal.get("owner_id") for m in sources):
            continue
        old = constraints.get(proposal.get("replaces_constraint_id"))
        if proposal.get("replaces_constraint_id") and (not old or old["owner_id"] != proposal["owner_id"] or old["key"] != proposal["key"]):
            continue
        accepted["constraint_proposals"].append(proposal)
    return accepted
