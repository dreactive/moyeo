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
        except (RuntimeError, OSError, TypeError, KeyError) as exc:
            return None, attempts, type(exc).__name__
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
    missing = unresolved_messages(batch, grounded.proposals)
    if missing:
        grounded.issue_codes.append("unresolved_intent")
        grounded.rejected_message_ids = list(dict.fromkeys(grounded.rejected_message_ids + missing))
    report = dict(status='filtered' if grounded.issue_codes else 'ok', issue_codes=grounded.issue_codes,
                  rejected_message_ids=grounded.rejected_message_ids, attempts=attempts)
    return dict(grounded.proposals, extraction_report=report)


def unresolved_messages(batch, proposals):
    missing = []
    for assessment in batch.message_assessments:
        for intent in assessment.intents:
            field = {'place': 'item_proposals', 'condition': 'constraint_proposals'}.get(intent)
            if intent in ('region', 'unclear') or field and not any(assessment.message_id in p['source_message_ids'] for p in proposals[field]):
                missing.append(assessment.message_id)
    return list(dict.fromkeys(missing))
