def test_env_file_reads_keys_without_mutating_process(tmp_path, monkeypatch):
    from ai.settings import load_settings
    monkeypatch.delenv("APIFY_TOKEN", raising=False)
    path = tmp_path / ".env"
    path.write_text('# ignored\nAPIFY_TOKEN="test=value"\nUNKNOWN_SECRET=no\n', encoding="utf-8")
    settings = load_settings({"env_file": str(path)})
    assert settings["APIFY_TOKEN"] == "test=value" and "UNKNOWN_SECRET" not in settings
    import os
    assert "APIFY_TOKEN" not in os.environ
