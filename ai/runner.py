import asyncio
import time
from httpx import HTTPError
from datetime import datetime, timezone
from ai.trace import emit, terminate
from ai.candidates import build_candidates, select_candidate, grounded_options, valid_options
from ai.tools.context import build_tool_context
from ai.tools.validation import validate_arguments
from ai.context import build_context
from ai.questions import question, valid_questions
from ai.outcome import assemble_result, reuse_current_plan
from ai.result import empty_result
from ai.extraction import validate_extraction
from ai.assistance import assist_extraction
from ai.selection import apply_selection
from ai.planning import itinerary_arguments, next_route
from ai.cost_inputs import build_cost_inputs


async def extract_proposals(task, model, emit_trace):
    error = None
    try:
        raw = await asyncio.to_thread(model.generate_json, {"phase": "extract", "context": task})
    except ValueError as exc:
        raw, error = {}, type(exc).__name__
    output = assist_extraction(raw, task)
    await emit(emit_trace, task, 0, "decision", None,
               dict(goal=task["goal"], candidates=[], selected_index=None, scores=[],
                    model_mode=getattr(model, "mode", "unknown"), base_versions=task["base_versions"],
                    extraction_mode="rule-assisted", model_format_error=error,
                    model_proposal_counts={k: len(v) for k, v in raw.items() if isinstance(v, list)}))
    return output


async def run_agent(task, model, tools, emit_trace):
    task = build_context(task, [])
    task, selection_questions = apply_selection(task)
    result = empty_result(task)
    if selection_questions:
        result["questions"] = valid_questions(task, selection_questions)
        await terminate(emit_trace, task, 0, model, "selection_needs_input")
        return result
    if hasattr(tools, "restore"):
        tools.restore(task)
    if task["config"].get("transport", "car") != "car":
        result["completion"] = "unsupported"
        return result
    try:
        result.update(await extract_proposals(task, model, emit_trace))
        result["questions"].extend(q for q in task["questions"] if q["status"] == "open")
        task["_new_item_refs"] = [i["client_ref"] for i in result["item_proposals"] if not i.get("existing_item_id")]
        task["items"].extend(dict(i, id=i["client_ref"], item_version=1) for i in result["item_proposals"]
                             if not i.get("existing_item_id"))
        if hasattr(tools, "restore"):
            tools.restore(task)
        message_only = task["goal"] in ("new_message", "message_created", "remaining_messages") and not result["item_proposals"]
        if task["goal"] in ("chat", "messages", "extract") or message_only:
            result["completion"] = "needs_input" if result["questions"] else "done"
        else:
            await run_steps(task, model, tools, emit_trace, result)
    except (ValueError, KeyError, TypeError, RuntimeError, OSError, HTTPError) as error:
        await terminate(emit_trace, task, 0, model, type(error).__name__)
    result["questions"] = valid_questions(task, result["questions"], result["item_proposals"])
    return result


async def run_steps(task, model, tools, emit_trace, result):
    if reuse_current_plan(task, result):
        return
    task = build_context(task, [])
    task["observations"] = [o for o in task["observations"] if o["tool_name"] not in ("build_itinerary", "calculate_costs")]
    if hasattr(tools, "restore"):
        tools.restore(task)
    for step in range(1, 21):
        context = build_context(task, result["observations"])
        action = await choose_action(context, model, emit_trace, step)
        if action["action"] != "tool":
            result["completion"] = "unsupported" if action["action"] == "unsupported" else "needs_input"
            result["questions"].extend(build_cost_inputs(context)[1])
            break
        observation = await execute_selected(task, action, tools, emit_trace, step)
        result["observations"].append(observation)
        if assemble_result(task, result):
            break
    else:
        await terminate(emit_trace, task, 20, model, "action_limit")


async def generate_candidates(context, model, emit_trace, step):
    context = build_tool_context(context)
    context["needed_route"] = next_route(context)
    context["available_calculations"] = dict(build_itinerary=itinerary_arguments(context),
                                             calculate_costs=build_cost_inputs(context)[0])
    generated = await asyncio.to_thread(model.generate_json, {"phase": "actions", "context": context})
    context["generated_candidates"] = generated.get("candidates", [])
    candidates = valid_options(context, build_candidates(context) + grounded_options(context))
    await emit(emit_trace, context, step, "decision", None,
               dict(goal=context["goal"], candidates=candidates, selected_index=None, scores=[],
                    model_mode=getattr(model, "mode", "unknown"), base_versions=context["base_versions"]))
    return candidates


async def choose_action(context, model, emit_trace, step):
    context = build_tool_context(context)
    context["needed_route"] = next_route(context)
    context["available_calculations"] = dict(build_itinerary=itinerary_arguments(context),
                                             calculate_costs=build_cost_inputs(context)[0])
    generated = await asyncio.to_thread(model.generate_json, {"phase": "actions", "context": context})
    context["generated_candidates"] = generated.get("candidates", [])
    candidates = valid_options(context, build_candidates(context) + grounded_options(context))
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
    observation = dict(tool_name=name, arguments=arguments, result=result,
                       observed_at=datetime.now(timezone.utc).isoformat(), source_refs=refs)
    if hasattr(tools, "remember"):
        tools.remember(observation)
    return observation
