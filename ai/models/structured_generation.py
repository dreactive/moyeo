"""JSON-schema token filtering; only imported by local extraction generation."""
from functools import lru_cache
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import (
    build_token_enforcer_tokenizer_data,
    build_transformers_prefix_allowed_tokens_fn,
)


@lru_cache(maxsize=2)
def tokenizer_data(tokenizer):
    return build_token_enforcer_tokenizer_data(tokenizer)


def build_extraction_prefix(tokenizer, schema, source_text=""):
    return build_transformers_prefix_allowed_tokens_fn(tokenizer_data(tokenizer), schema_parser(schema, source_text))



def schema_parser(schema, source_text=''):
    from lmformatenforcer import CharacterLevelParserConfig
    config = CharacterLevelParserConfig()
    config.alphabet = ''.join(dict.fromkeys(config.alphabet + source_text))
    return JsonSchemaParser(schema, config=config)
