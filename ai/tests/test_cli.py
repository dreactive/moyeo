import json
import subprocess
import sys


def test_cli_executes_fixture_selected_calls_and_keeps_missing_cost_unknown(tmp_path):
    path = tmp_path / "result.json"
    process = subprocess.run([sys.executable, "-m", "ai.cli", "run", "--task",
                              "ai/fixtures/agent-task.json", "--model", "fake",
                              "--providers", "fixture", "--output", str(path)],
                             capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    result = json.loads(path.read_text(encoding="utf-8"))
    assert [o["tool_name"] for o in result["observations"]] == [
        "get_car_route", "get_car_route", "get_car_route", "get_car_route", "build_itinerary", "calculate_costs"]
    assert result["observations"][0]["arguments"] == dict(from_ref="anchor:origin", to_ref="fixture:place-a",
        departure_at="2026-11-21T09:00:00+09:00")
    assert result["completion"] == "needs_input" and result["plan_draft"]["validation"] == "needs_input"
    assert result["plan_draft"]["cost"]["total_krw"] is None
    assert result["decision_report"]["action"] == "tool"
    assert "fake/fixture" in process.stdout


def test_provider_cli_missing_key_is_explicit_not_run(tmp_path):
    settings, output = tmp_path / ".env", tmp_path / "probe.json"
    settings.write_text("APIFY_TOKEN=\n", encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "ai.providers.probe", "--provider", "apify",
        "--region", "여수", "--env-file", str(settings), "--output", str(output)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["status"] == "not_run" and report["matched_place_count"] == 0


def test_replay_cli_writes_assertions_and_modes(tmp_path):
    cases, output = tmp_path / "cases.jsonl", tmp_path / "eval.json"
    case = dict(id="chat", messages=[dict(id="hello", author_id="u1", text="안녕")],
        actions=[{"kind": "patch_task", "patch": {"goal": "new_message", "questions": [],
            "items": [], "current_plan": None, "observations": []}}],
        expected={"completion": "done", "observations.length": 0})
    cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "ai.eval.replay", "--model", "fake",
        "--providers", "fixture", "--cases", str(cases), "--output", str(output)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed_cases"] == 1 and report["model_mode"] == "fake" and report["git_sha"]
