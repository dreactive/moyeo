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


def test_auxiliary_settings_follow_model_mode_and_preserve_blank_key(tmp_path, monkeypatch):
    from backend.config import read_settings
    for key in ('MODEL_BACKEND', 'AUXILIARY_BACKEND', 'AUX_MODEL', 'AUX_REASONING_EFFORT', 'OPENAI_API_KEY', 'AUX_BASE_URL'):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / '.env'
    path.write_text('MODEL_BACKEND=local_qwen\nOPENAI_API_KEY=\n', encoding='utf-8')
    config = read_settings(path)['runtime_config']
    assert config['auxiliary_backend'] == 'external'
    assert config['aux_model'] == 'gpt-6-luna'
    assert config['aux_reasoning_effort'] == 'none'
    assert config['aux_api_key'] == ''
    assert config['aux_base_url'] is None
    path.write_text('MODEL_BACKEND=fake\n', encoding='utf-8')
    assert read_settings(path)['runtime_config']['auxiliary_backend'] == 'fixture'


def test_auxiliary_environment_overrides_are_passed_to_runtime(tmp_path, monkeypatch):
    from backend.config import read_settings
    monkeypatch.setenv('AUXILIARY_BACKEND', 'external')
    monkeypatch.setenv('AUX_MODEL', 'configured-model')
    monkeypatch.setenv('AUX_REASONING_EFFORT', 'low')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-credential')
    monkeypatch.setenv('AUX_BASE_URL', 'https://example.test/api')
    config = read_settings(tmp_path / 'absent.env')['runtime_config']
    assert {key: config[key] for key in ('auxiliary_backend', 'aux_model', 'aux_reasoning_effort', 'aux_base_url')} == {
        'auxiliary_backend': 'external', 'aux_model': 'configured-model',
        'aux_reasoning_effort': 'low', 'aux_base_url': 'https://example.test/api'}
    assert config['aux_api_key'] == 'test-only-credential'
