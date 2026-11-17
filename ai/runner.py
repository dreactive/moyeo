import asyncio
import time
from datetime import datetime, timezone
from ai.trace import emit
from ai.candidates import build_candidates, select_candidate
from ai.tools.context import build_tool_context
from ai.tools.validation import validate_arguments


async def choose_action(context, model, emit_trace, step):
    context = build_tool_context(context)
    generated = await asyncio.to_thread(model.generate_json, {"phase": "actions", "context": context})
    context["generated_candidates"] = generated.get("candidates", [])
    candidates = build_candidates(context)
    scores = await asyncio.to_thread(model.score_candidates, context, candidates)
    index = select_candidate(candidates, scores)
    action = candidates[index]
    await emit(emit_trace, context, step, "decision", None,
               dict(goal=context["goal"], candidates=candidates, selected_index=index, scores=scores,
                    model_mode=getattr(model, "mode", "unknown"), base_versions=context["base_versions"]))
    if action["action"] == "tool":
        validate_arguments(action["tool_name"], action["arguments"], context)
    return action


async def execute_selected(task, action, tools, emit_trace, step):
    name, arguments = action["tool_name"], action["arguments"]
    call_id = f"{task['run_id']}:{step}"
    await emit(emit_trace, task, step, "tool_call", call_id, dict(tool_name=name, arguments=arguments))
    started = time.perf_counter()
    result = await tools.execute(name, arguments)
    refs = [e["id"] for e in result.get("evidence", [])]
    if result.get("evidence_id"):
        refs.append(result["evidence_id"])
    await emit(emit_trace, task, step, "tool_result", call_id,
               dict(tool_name=name, normalized_result=result, source_refs=refs,
                    duration_ms=round((time.perf_counter() - started) * 1000, 2)))
    return dict(tool_name=name, arguments=arguments, result=result,
                observed_at=datetime.now(timezone.utc).isoformat(), source_refs=refs)
