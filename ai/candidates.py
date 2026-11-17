import math


def select_candidate(candidates, scores):
    if not candidates or len(scores) != len(candidates):
        raise ValueError("Candidate score count mismatch")
    if any(isinstance(s, bool) or not isinstance(s, (float, int)) or not math.isfinite(s) for s in scores):
        raise ValueError("Nonfinite or invalid judge score")
    return max(range(len(candidates)), key=scores.__getitem__)


def build_candidates(context):
    messages = {m["id"] for m in context["recent_messages"]}
    refs = {r for o in context["observations"] for r in o.get("source_refs", [])}
    refs.update(context.get("places", {}))
    accepted = []
    required = {"action", "reason", "tool_name", "arguments", "source_message_ids", "source_refs"}
    for c in context.get("generated_candidates", []):
        if not isinstance(c, dict) or set(c) != required:
            continue
        if c["action"] not in ("tool", "ask", "direct", "wait", "finish", "unsupported"):
            continue
        if set(c["source_message_ids"]) <= messages and set(c["source_refs"]) <= refs:
            accepted.append(c)
    return accepted
