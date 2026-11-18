"""JSON-schema token filtering; only imported by local extraction generation."""
from functools import lru_cache
from lmformatenforcer import JsonSchemaParser
from lmformatenforcer.integrations.transformers import (
    build_token_enforcer_tokenizer_data,
    build_transformers_prefix_allowed_tokens_fn,
)


def tokenizer_data(tokenizer):
    return build_token_enforcer_tokenizer_data(tokenizer)


def build_extraction_prefix(tokenizer, schema):
    return build_transformers_prefix_allowed_tokens_fn(tokenizer_data(tokenizer), JsonSchemaParser(schema))
