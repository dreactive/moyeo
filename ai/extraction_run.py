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


def extraction_output(batch, attempts, error, task):
    from ai.grounding import ground_extraction
    if batch is None:
        return dict(constraint_proposals=[], item_proposals=[], support_observations=[], questions=[],
                    completion='needs_input', last_processed_message_id=None,
                    extraction_report=dict(status='failed', issue_codes=[error], rejected_message_ids=[m['id'] for m in task['recent_messages']], attempts=attempts))
    grounded = ground_extraction(batch, task)
    report = dict(status='filtered' if grounded.issue_codes else 'ok', issue_codes=grounded.issue_codes,
                  rejected_message_ids=grounded.rejected_message_ids, attempts=attempts)
    return dict(grounded.proposals, extraction_report=report)
