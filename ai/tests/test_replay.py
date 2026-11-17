def test_replay_paths_compare_real_result_values_and_lengths():
    from ai.eval.replay import read_path
    assert read_path({"items": [{"cost": None}]}, "items.0.cost") is None
    assert read_path({"items": [1, 2]}, "items.length") == 2
    assert read_path({"items": []}, "items.5") is None


async def test_replay_reports_modes_and_unexecuted_models_honestly():
    from ai.eval.replay import replay_case
    case = dict(id="chat", members=[], trip={}, messages=[], actions=[
        {"kind": "patch_task", "patch": {"goal": "new_message", "questions": []}}],
        expected={"completion": "done", "observations.length": 0})
    report = await replay_case(case, "fake", "fixture")
    assert report["passed"] and report["model_mode"] == "fake" and report["provider_mode"] == "fixture"
    assert report["metrics"]["tool_calls"] == 0
    missing = await replay_case(case, "local_qwen", "live", config={"base_model_path": "missing", "adapter_path": "missing"})
    assert missing["passed"] is False and missing["status"] == "not_run" and missing["limitations"]
