import pytest
from pydantic import ValidationError


def test_extraction_requires_all_lists_and_strict_fields():
    from ai.extraction_schema import ExtractionBatch
    with pytest.raises(ValidationError):
        ExtractionBatch.model_validate({'constraint_proposals': []})
    empty = dict(message_assessments=[], constraint_proposals=[], item_proposals=[], support_observations=[])
    assert ExtractionBatch.model_validate(empty).item_proposals == []
    with pytest.raises(ValidationError):
        ExtractionBatch.model_validate(dict(empty, unexpected=True))

def test_small_message_schema_preserves_unsupported_condition_keys():
    from ai.extraction_schema import MessageFacts
    facts = MessageFacts.model_validate(dict(places=[], conditions=[dict(key='wheelchair_access', value=True)], intents=['condition']))
    assert facts.conditions[0].key == 'wheelchair_access'

def test_fake_extraction_matches_strict_batch_schema():
    from ai.models.fake_extraction import fixture_batch
    from ai.extraction_schema import ExtractionBatch
    from ai.tests.test_place_route_tools import task
    batch = ExtractionBatch.model_validate(fixture_batch({}, task()))
    assert batch.constraint_proposals[0].value == 200000

async def test_validated_batch_has_bounded_retry():
    from ai.extraction_run import validated_batch
    from ai.tests.test_place_route_tools import task
    class Broken:
        def generate_json(self, request): return {}
    batch, attempts, error = await validated_batch(task(), Broken())
    assert batch is None and attempts == 2 and error == 'ValidationError'
