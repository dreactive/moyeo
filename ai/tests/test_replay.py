def test_replay_paths_compare_real_result_values_and_lengths():
    from ai.eval.replay import read_path
    assert read_path({"items": [{"cost": None}]}, "items.0.cost") is None
    assert read_path({"items": [1, 2]}, "items.length") == 2
    assert read_path({"items": []}, "items.5") is None
