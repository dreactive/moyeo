import asyncio
import time
from datetime import datetime, timezone
from ai.trace import emit


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
