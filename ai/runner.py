import asyncio
import time
from datetime import datetime, timezone
from ai.trace import emit
from ai.candidates import build_candidates, select_candidate
from ai.tools.context import build_tool_context
from ai.tools.validation import validate_arguments
from ai.context import build_context
from ai.questions import question
from ai.outcome import assemble_result
from ai.result import empty_result
from ai.extraction import validate_extraction


async def run_agent(task, model, tools, emit_trace):
    task = build_context(task, [])
    result = empty_result(task)
    if task["config"].get("transport", "car") != "car":
        result["completion"] = "unsupported"
        return result
    try:
        extraction = await asyncio.to_thread(model.generate_json, {"phase": "extract", "context": task})
        result.update(validate_extraction(extraction, task))
        if task["goal"] in ("chat", "messages", "extract"):
            result["completion"] = "needs_input" if result["questions"] else "done"
        else:
            await run_steps(task, model, tools, emit_trace, result)
    except (ValueError, KeyError, TypeError, RuntimeError, OSError) as error:
        result["questions"].append(question("constraint_value", None,
                                           f"모델/도구 검증 실패: {type(error).__name__}. 입력/설정을 확인해주세요."))
    return result


async def run_steps(task, model, tools, emit_trace, result):
    for step in range(1, 21):
        context = build_context(task, result["observations"])
        action = await choose_action(context, model, emit_trace, step)
        if action["action"] != "tool":
            result["completion"] = "unsupported" if action["action"] == "unsupported" else "needs_input"
            result["questions"].append(question("constraint_value", None, action["reason"]))
            break
        observation = await execute_selected(task, action, tools, emit_trace, step)
        result["observations"].append(observation)
        if assemble_result(task, result):
            break
    else:
        result["questions"].append(question("constraint_value", None, "20회 행동 상한에 도달했습니다."))


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
