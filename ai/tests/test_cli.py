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
