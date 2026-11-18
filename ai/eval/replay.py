"""Standalone boundary replay, never a substitute for Backend confirmations."""
import json
import time
from pathlib import Path
from copy import deepcopy
from ai.runtime import create_runtime
import subprocess
import sys
import argparse
import asyncio


async def evaluate(cases, model_mode, provider_mode, config):
    root = Path(__file__).resolve().parents[2]
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--", "ai", "docs/verification/ai.md"],
                           cwd=root, capture_output=True, text=True, check=True).stdout
    runtime, reports, started = None, [], time.perf_counter()
    try:
        runtime = create_runtime(dict(config, model_backend=model_mode, provider_mode=provider_mode))
        load_seconds = round(time.perf_counter() - started, 4)
        for case in cases:
            reports.append(await replay_case(case, model_mode, provider_mode, config, runtime))
    except (ValueError, RuntimeError, OSError) as error:
        reports = [dict(case_id=c["id"], passed=False, status="not_run", limitations=[type(error).__name__]) for c in cases]
        load_seconds = round(time.perf_counter() - started, 4)
    finally:
        if runtime is not None:
            await runtime.aclose()
    return dict(model_mode=model_mode, provider_mode=provider_mode, git_sha=sha, git_dirty=bool(dirty.strip()),
                python_version=sys.version.split()[0], model_load_seconds=load_seconds, total_cases=len(cases),
                passed_cases=sum(r["passed"] for r in reports), passed=bool(reports) and all(r["passed"] for r in reports),
                cases=reports)


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
        report.update(status="executed", run_ids=[result["run_id"]], result=result, events=events)
        report["assertions"] = [dict(path=path, expected=expected, actual=read_path(result, path),
                                    passed=read_path(result, path) == expected)
                                for path, expected in case.get("expected", {}).items()]
        report["metrics"] = dict(tool_calls=len(result["observations"]),
            selected_actions=sum(e["event"] == "decision" and e["payload"].get("selected_index") is not None for e in events),
            seconds=round(time.perf_counter() - started, 4))
        report["passed"] = bool(report["assertions"]) and all(a["passed"] for a in report["assertions"])
        report["limitations"] = ["Standalone AI boundary only; no official confirmation",
                                 "Auxiliary: " + result.get('extraction_report', {}).get('backend', 'unknown'),
                                 "fixture values are not live proof" if provider_mode == "fixture" else "Live tool observations must be checked separately"]
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


async def main(args):
    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding="utf-8").splitlines() if line.strip()]
    report = await evaluate(cases, args.model, args.providers, dict(base_model_path=args.base_model_path,
                            adapter_path=args.adapter_path, env_file=args.env_file))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{args.model}/{args.providers}: {report['passed_cases']}/{report['total_cases']} cases")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["fake", "local_qwen"], default="fake")
    parser.add_argument("--providers", choices=["fixture", "live"], default="fixture")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-model-path")
    parser.add_argument("--adapter-path")
    parser.add_argument("--env-file")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
