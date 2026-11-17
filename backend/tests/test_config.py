def test_settings_load_env_file_without_exposing_provider_secrets(tmp_path, monkeypatch):
    from backend.config import read_settings
    path = tmp_path / '.env'
    path.write_text('KAKAO_JAVASCRIPT_KEY=public-map\nKAKAO_REST_API_KEY=server-secret\nAGENT_MODE=local_ai\nMODEL_BACKEND=fake\nPROVIDER_MODE=fixture\n', encoding='utf-8')
    monkeypatch.setenv('BACKEND_DB', ':memory:')
    settings = read_settings(path)
    assert settings['database_path'] == ':memory:'
    assert settings['public_map_key'] == 'public-map'
    assert settings['runtime_config']['env_file'] == str(path.resolve())
    assert 'server-secret' not in str(settings)
