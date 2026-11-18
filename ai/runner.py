import asyncio
import time
from httpx import HTTPError
from datetime import datetime, timezone
from ai.trace import emit, terminate
from ai.candidates import build_candidates, grounded_options, valid_options
from ai.tools.context import build_tool_context
from ai.context import build_context
from ai.questions import valid_questions
from ai.result import empty_result
from ai.assistance import assist_extraction
from ai.selection import apply_selection
from ai.planning import itinerary_arguments, next_route
from ai.cost_inputs import build_cost_inputs


async def extract_proposals(task, model, emit_trace):
    from ai.extraction_run import validated_batch, extraction_output
    batch, attempts, error = await validated_batch(task, model)
    output = extraction_output(batch, attempts, error, task)
    await emit(emit_trace, task, 0, "decision", None,
               dict(goal=task["goal"], candidates=[], selected_index=None, scores=[],
                    model_mode=getattr(model, "mode", "unknown"), base_versions=task["base_versions"],
                    extraction_mode="schema-grounded", model_format_error=error,
                    schema_version="1", decoder_mode="json-schema" if getattr(model, "mode", "unknown") == "local_qwen" else "fixture-schema",
                    model_proposal_counts={key:len(getattr(batch, key)) if batch else 0 for key in ("item_proposals", "constraint_proposals", "support_observations")}, extraction_report=output["extraction_report"]))
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
        if result["extraction_report"]["status"] == "failed":
            return result
        result["questions"].extend(q for q in task["questions"] if q["status"] == "open")
        task["_new_item_refs"] = [i["client_ref"] for i in result["item_proposals"] if not i.get("existing_item_id")]
        task["items"].extend(dict(i, id=i["client_ref"], item_version=1) for i in result["item_proposals"]
                             if not i.get("existing_item_id"))
        if hasattr(tools, "restore"):
            tools.restore(task)
        message_only = task["goal"] in ("new_message", "message_created", "remaining_messages") and not result["item_proposals"]
        if task["goal"] in ("chat", "messages", "extract") or message_only:
            result["completion"] = "needs_input" if result["questions"] or result["extraction_report"]["status"] != "ok" else "done"
        else:
            await run_steps(task, model, tools, emit_trace, result)
    except (ValueError, KeyError, TypeError, RuntimeError, OSError, HTTPError) as error:
        await terminate(emit_trace, task, 0, model, type(error).__name__)
    result["questions"] = valid_questions(task, result["questions"], result["item_proposals"])
    return result


async def run_steps(task, model, tools, emit_trace, result):
    task = build_context(task, [])
    task["observations"] = [o for o in task["observations"] if o["tool_name"] not in ("build_itinerary", "calculate_costs")]
    result["candidates"] = await generate_candidates(task, model, emit_trace, 1)


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


async def execute_selected(task, action, tools, emit_trace, step, origin='manual'):
    name, arguments = action["tool_name"], action["arguments"]
    call_id = f"{task['run_id']}:{step}"
    await emit(emit_trace, task, step, "tool_call", call_id, dict(tool_name=name, arguments=arguments, selection_origin=origin))
    started = time.perf_counter()
    result = await tools.execute(name, arguments)
    refs = [e["id"] for e in result.get("evidence", [])]
    if result.get("evidence_id"):
        refs.append(result["evidence_id"])
    await emit(emit_trace, task, step, "tool_result", call_id,
               dict(tool_name=name, normalized_result=result, source_refs=refs,
                    execution_source=getattr(tools, 'last_execution_source', 'unknown'),
                    duration_ms=round((time.perf_counter() - started) * 1000, 2)))
    observation = dict(tool_name=name, arguments=arguments, result=result,
                       observed_at=datetime.now(timezone.utc).isoformat(), source_refs=refs)
    if hasattr(tools, "remember"):
        tools.remember(observation)
    return observation
