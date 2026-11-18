"""Attach code-owned identities and original evidence to compact Qwen facts."""
from ai.extraction_schema import MessageFacts
from ai.grounding import normalized


def facts_to_batch(raw, message, task):
    facts = MessageFacts.model_validate(raw)
    evidence = dict(message_id=message['id'], quote=message['text'])
    items = [dict(title=name, mention_text=name, existing_item_id=next((i['id'] for i in task['items'] if normalized(i['title']) == normalized(name)), None), evidence=evidence) for name in facts.places]
    return dict(message_assessments=[dict(message_id=message['id'], intents=facts.intents)],
                item_proposals=items, constraint_proposals=[], support_observations=[])
