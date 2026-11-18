"""Attach code-owned identities and original evidence to compact Qwen facts."""
from ai.extraction_schema import MessageFacts
from ai.grounding import normalized


def facts_to_batch(raw, message, task):
    facts = MessageFacts.model_validate(raw)
    evidence = dict(message_id=message['id'], quote=message['text'])
    items = [dict(title=name, mention_text=name, existing_item_id=next((i['id'] for i in task['items'] if normalized(i['title']) == normalized(name)), None), evidence=evidence) for name in facts.places]
    return dict(message_assessments=[dict(message_id=message['id'], intents=facts.intents)],
                item_proposals=items, constraint_proposals=[condition_proposal(fact, message, task, evidence) for fact in facts.conditions], support_observations=[])


def condition_proposal(fact, message, task, evidence):
    family = ('budget', 'budget_krw') if fact.key in ('budget', 'budget_krw') else (fact.key,)
    old = next((c for c in task['constraints'] if c['owner_id'] == message['author_id'] and c['key'] in family and c.get('status') != 'superseded'), None)
    return dict(owner_id=message['author_id'], key=old['key'] if old else fact.key, value=fact.value,
                kind='hard', replaces_constraint_id=old['id'] if old else None, evidence=evidence)
