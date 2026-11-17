import json
from pathlib import Path


def test_canonical_agent_input_result_fields():
    from ai.result import empty_result
    task = json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))
    result = empty_result(task)
    expected = json.loads(Path("docs/contracts/examples/agent-result.example.json").read_text(encoding="utf-8"))
    assert set(result) == set(expected)
    assert result["run_id"] == "run-fixture"
    assert result["base_versions"] == task["base_versions"]
    assert result["completion"] == "needs_input"
    assert result["last_processed_message_id"] == "m4"
    json.dumps(result, allow_nan=False)
