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
