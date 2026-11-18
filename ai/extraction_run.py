"""Bounded structural retries; never converts failed generation into rule success."""
import asyncio
from ai.extraction_schema import ExtractionBatch
from ai.grounding import validate_assessments


async def validated_batch(task, model):
    error = None
    for attempts in (1, 2):
        try:
            raw = await asyncio.to_thread(model.generate_json, dict(phase='extract', context=task))
            if getattr(model, 'mode', None) == 'fake':
                from ai.models.fake_extraction import fixture_batch
                raw = fixture_batch(raw, task)
            batch = ExtractionBatch.model_validate(raw)
            validate_assessments(batch, task)
            return batch, attempts, None
        except ValueError as exc:
            error = type(exc).__name__
    return None, attempts, error
