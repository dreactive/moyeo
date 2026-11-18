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

def test_extract_generation_options_restrict_json_schema(monkeypatch):
    import ai.models.qwen_generation as module
    import ai.models.structured_generation as decoding
    monkeypatch.setattr(decoding, 'build_extraction_prefix', lambda tokenizer, schema, source_text: schema)
    options = module.extraction_options({'phase': 'extract'}, None)
    assert options['prefix_allowed_tokens_fn']['additionalProperties'] is False
    assert module.extraction_options({'phase': 'actions'}, None) == {}

def test_source_korean_characters_are_allowed_in_bounded_strings():
    from ai.models.structured_generation import schema_parser
    parser = schema_parser({'type':'string','minLength':1,'maxLength':20}, '오동도')
    for character in '"오동도"':
        assert character in parser.get_allowed_characters()
        parser = parser.add_character(character)
    assert parser.can_end()
