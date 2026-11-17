from datetime import datetime, timezone

PRIVATE = ("token", "api_key", "servicekey", "authorization", "password", "secret",
           "reasoning", "chain_of_thought", "raw_response")


def redact(value):
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if not any(p in k.lower() for p in PRIVATE)}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


async def emit(sink, task, step, event, call_id, payload):
    if sink:
        await sink(dict(run_id=task["run_id"], step=step, event=event, call_id=call_id,
                        created_at=datetime.now(timezone.utc).isoformat(), payload=redact(payload)))


async def terminate(sink, task, step, model, reason):
    await emit(sink, task, step, "decision", None, dict(goal=task["goal"], candidates=[],
        selected_index=None, scores=[], model_mode=getattr(model, "mode", "unknown"),
        base_versions=task["base_versions"], termination=reason))
