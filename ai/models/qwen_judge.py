"""Service input checks around the unchanged supplied yes/no judge."""
import json
import math

from ai.tools.definitions import TOOL_DEFINITIONS


def candidate_reply(candidate):
    if candidate.get("action") == "tool":
        name, arguments = candidate.get("tool_name"), candidate.get("arguments")
        if not isinstance(name, str) or not name.strip() or not isinstance(arguments, dict):
            raise ValueError("Judge candidate needs an actual tool name and arguments")
        return json.dumps({"name": name, "arguments": arguments}, ensure_ascii=False, allow_nan=False)
    if candidate.get("action") not in ("ask", "unsupported", "direct"):
        raise ValueError("Unsupported judge candidate action")
    reason = candidate.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("Judge candidate needs its actual response reason")
    return reason


def score_candidates(model, tokenizer, context, candidates):
    from submission import judge

    if not 1 <= len(candidates) <= 4:
        raise ValueError("Judge requires between one and four real candidates")
    tools = context.get("tools", TOOL_DEFINITIONS)
    question = json.dumps({k: v for k, v in context.items() if k != "tools"},
                          ensure_ascii=False, allow_nan=False)
    choices = [candidate_reply(candidate) for candidate in candidates]
    causal = judge.causal_lm(model)
    maximum = min(32768, getattr(causal.config, "max_position_embeddings", 32768))
    for choice in choices:
        tokens = tokenizer.encode(judge.judge_prompt(question, tools, choice), add_special_tokens=False)
        if len(tokens) > maximum:
            raise ValueError(f"Judge input exceeds token budget ({len(tokens)} > {maximum}); scoring deferred")
    scores = judge.judge_scores(model, tokenizer, question, tools, choices)
    if len(scores) != len(candidates):
        raise ValueError("Judge score count differs from the actual candidate count")
    scores = [float(score) for score in scores]
    if not all(math.isfinite(score) for score in scores):
        raise ValueError("Judge returned a nonfinite score")
    return scores
