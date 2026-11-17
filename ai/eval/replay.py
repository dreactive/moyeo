"""Standalone boundary replay, never a substitute for Backend confirmations."""
import json
import time
from pathlib import Path
from copy import deepcopy
from ai.runtime import create_runtime


def case_task(case):
    task = json.loads((Path(__file__).parents[1] / "fixtures/agent-task.json").read_text(encoding="utf-8"))
    task["run_id"] = "eval:" + case["id"]
    task["members"] = deepcopy(case.get("members", task["members"]))
    task["config"].update(deepcopy(case.get("trip", {})))
    task["recent_messages"] = deepcopy(case.get("messages", []))
    for action in case.get("actions", []):
        if action["kind"] != "patch_task":
            raise ValueError("Replay actions patch input only; no Backend state simulation")
        task.update(deepcopy(action["patch"]))
    return task


async def replay_case(case, model_mode, provider_mode, config=None, runtime=None):
    report = dict(case_id=case["id"], model_mode=model_mode, provider_mode=provider_mode, passed=False,
                  status="not_run", run_ids=[], assertions=[], metrics={}, limitations=[])
    owned, started, events = runtime is None, time.perf_counter(), []
    async def emit(event):
        events.append(event)
    try:
        runtime = runtime or create_runtime(dict(config or {}, model_backend=model_mode, provider_mode=provider_mode))
        result = await runtime.run(case_task(case), emit)
        report.update(status="executed", run_ids=[result["run_id"]], result=result)
        report["assertions"] = [dict(path=path, expected=expected, actual=read_path(result, path),
                                    passed=read_path(result, path) == expected)
                                for path, expected in case.get("expected", {}).items()]
        report["metrics"] = dict(tool_calls=len(result["observations"]),
            selected_actions=sum(e["event"] == "decision" and e["payload"].get("selected_index") is not None for e in events),
            seconds=round(time.perf_counter() - started, 4))
        report["passed"] = bool(report["assertions"]) and all(a["passed"] for a in report["assertions"])
        report["limitations"] = ["Standalone AI boundary only; no official confirmation",
                                 "rule-assisted extraction", "fixture values are not live proof" if provider_mode == "fixture" else "Live tool observations must be checked separately"]
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as error:
        report["limitations"].append("Execution unavailable: " + type(error).__name__)
    finally:
        if owned and runtime is not None:
            await runtime.aclose()
    return report


def read_path(value, path):
    for part in path.split("."):
        try:
            if isinstance(value, list):
                value = len(value) if part == "length" else value[int(part)]
            else:
                value = value.get(part)
        except (IndexError, ValueError, TypeError, AttributeError):
            return None
    return value
