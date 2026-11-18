"""Keep the small local model focused on one message's facts per generation."""
from ai.extraction_projection import facts_to_batch
from ai.models.qwen_generation import generate_object


def generate_extraction(model, tokenizer, request):
    batch = dict(message_assessments=[], item_proposals=[], constraint_proposals=[], support_observations=[])
    for message in request['context']['recent_messages']:
        context = dict(request['context'], recent_messages=[message])
        raw = generate_object(model, tokenizer, dict(request, context=context))
        projected = facts_to_batch(raw, message, context)
        for key in batch:
            batch[key].extend(projected[key])
    return batch
