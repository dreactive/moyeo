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


async def test_runtime_reuses_model_and_chat_never_calls_tools():
    from ai.runtime import create_runtime
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    task = json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))
    task["goal"] = "chat"
    model = runtime.model
    result = await runtime.run(task, None)
    assert result["constraint_proposals"][0]["owner_id"] == "u1"
    assert result["observations"] == [] and runtime.model is model
    await runtime.aclose()
    await runtime.aclose()
    assert model.closed


async def test_fake_fixture_runtime_produces_unscored_candidates_and_mode_trace():
    from ai.runtime import create_runtime
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    task = json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))
    events = []
    async def sink(event):
        events.append(event)
    result = await runtime.run(task, sink)
    await runtime.aclose()
    assert result["plan_draft"] is None and result["observations"] == []
    assert result["candidates"][0]["tool_name"] == "get_car_route"
    assert result["completion"] == "needs_input"
    assert {e["payload"]["model_mode"] for e in events if e["event"] == "decision"} == {"fake"}


def test_local_qwen_runtime_needs_local_weights_without_downloading():
    import pytest
    from ai.runtime import create_runtime
    with pytest.raises(ValueError, match="local"):
        create_runtime({"model_backend": "local_qwen", "provider_mode": "fixture",
                        "base_model_path": "missing", "adapter_path": "missing"})


async def test_new_message_chitchat_waits_without_lookup():
    from ai.runtime import create_runtime
    task = json.loads(Path("ai/fixtures/agent-task.json").read_text(encoding="utf-8"))
    task.update(goal="new_message", current_plan=None, items=[], observations=[], questions=[])
    task["recent_messages"] = [dict(task["recent_messages"][0], text="좋은 아침")]
    runtime = create_runtime({"model_backend": "fake", "provider_mode": "fixture"})
    result = await runtime.run(task, None)
    await runtime.aclose()
    assert result["completion"] == "done" and result["observations"] == [] and result["plan_draft"] is None
