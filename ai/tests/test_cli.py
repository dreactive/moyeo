import json
import subprocess
import sys


def test_cli_labels_fixture_mode(tmp_path):
    path = tmp_path / "result.json"
    process = subprocess.run([sys.executable, "-m", "ai.cli", "run", "--task",
                              "ai/fixtures/agent-task.json", "--model", "fake",
                              "--providers", "fixture", "--output", str(path)],
                             capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(path.read_text(encoding="utf-8"))["completion"] == "needs_input"
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
    case = dict(id="chat", messages=[], actions=[{"kind": "patch_task", "patch": {
        "goal": "new_message", "questions": []}}], expected={"completion": "done"})
    cases.write_text(json.dumps(case) + "\n", encoding="utf-8")
    process = subprocess.run([sys.executable, "-m", "ai.eval.replay", "--model", "fake",
        "--providers", "fixture", "--cases", str(cases), "--output", str(output)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed_cases"] == 1 and report["model_mode"] == "fake" and report["git_sha"]
