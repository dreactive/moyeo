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


async def test_fake_fixture_runtime_without_torch_or_backend():
    from ai.runtime import create_runtime
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    task = json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))
    result = await runtime.run(task, None)
    assert result["room_id"] == task["room_id"]
    details = await runtime.execute_tool("get_place_details", {"place_ref": "fixture:place-a"}, task)
    assert details["place"]["name"] == "가상 A식당"
    await runtime.aclose()
