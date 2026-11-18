import pytest
pytest.importorskip('lmformatenforcer')


def test_schema_prefix_is_fresh_for_each_request(monkeypatch):
    import ai.models.structured_generation as module
    from lmformatenforcer.tokenenforcer import TokenEnforcerTokenizerData
    data = TokenEnforcerTokenizerData([(1, 'a', False)], lambda tokens: 'a', 0, False, 2)
    monkeypatch.setattr(module, 'tokenizer_data', lambda tokenizer: data)
    assert module.build_extraction_prefix(None, {'type': 'object'}) is not module.build_extraction_prefix(None, {'type': 'object'})


def test_tokenizer_vocabulary_is_reused(monkeypatch):
    import ai.models.structured_generation as module
    monkeypatch.setattr(module, 'build_token_enforcer_tokenizer_data', lambda tokenizer: object())
    tokenizer = object()
    assert module.tokenizer_data(tokenizer) is module.tokenizer_data(tokenizer)
