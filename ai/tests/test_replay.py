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


async def test_evaluation_reuses_one_runtime_and_records_revision(monkeypatch):
    import ai.eval.replay as module
    original, calls = module.create_runtime, []
    def factory(config):
        calls.append(config)
        return original(config)
    monkeypatch.setattr(module, "create_runtime", factory)
    case = dict(id="chat", members=[], trip={}, messages=[],
                actions=[{"kind": "patch_task", "patch": {"goal": "new_message", "questions": []}}],
                expected={"completion": "done"})
    report = await module.evaluate([case, dict(case, id="chat2")], "fake", "fixture", {})
    assert len(calls) == 1 and report["passed_cases"] == 2
    assert len(report["git_sha"]) == 40 and isinstance(report["git_dirty"], bool)
