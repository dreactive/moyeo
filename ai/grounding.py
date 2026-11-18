"""Evidence checks shared by model extraction and deterministic assistance."""
from dataclasses import dataclass
import unicodedata
from collections import Counter


@dataclass
class GroundedExtraction:
    proposals: dict
    issue_codes: list[str]
    rejected_message_ids: list[str]


def source_message(evidence, task):
    message = next((m for m in task['recent_messages'] if m['id'] == evidence['message_id']), None)
    members = {member['user_id'] for member in task['members']}
    return message if message and message['author_id'] in members and evidence['quote'] and evidence['quote'] in message['text'] else None


def normalized(text):
    return ''.join(unicodedata.normalize('NFC', text).split())


def project_item(proposal, task):
    message = source_message(proposal['evidence'], task)
    title, mention = normalized(proposal['title']), normalized(proposal['mention_text'])
    if title in ('점심', '저녁', '아침', '밥', '식사', '식당', '카페', '공원', '역', '여행') or title == normalized(task['config'].get('region', '')):
        return None
    if not message or title != mention or mention not in normalized(proposal['evidence']['quote']):
        return None
    return dict(client_ref='client:' + message['id'], existing_item_id=proposal['existing_item_id'],
                kind='place', title=proposal['title'], source_message_ids=[message['id']])


def project_condition(proposal, task):
    from ai.condition_grounding import condition_value
    message = source_message(proposal['evidence'], task)
    if not message or message['author_id'] != proposal['owner_id']:
        return None
    value = condition_value(proposal['key'], message['text'])
    if value is None or type(value) is not type(proposal['value']) or value != proposal['value']:
        return None
    return dict({k: v for k, v in proposal.items() if k != 'evidence'}, source_message_ids=[message['id']])


def project_many(proposals, projector, task):
    accepted, rejected = [], []
    for proposal in proposals:
        result = projector(proposal, task)
        if result is None:
            rejected.append(proposal['evidence']['message_id'])
        else:
            accepted.append(result)
    return accepted, rejected


def ground_extraction(batch, task):
    validate_assessments(batch, task)
    raw = batch.model_dump()
    items, item_errors = project_many(raw['item_proposals'], project_item, task)
    counts = Counter()
    for item in items:
        ref = item['client_ref']
        item['client_ref'] += ':' + str(counts[ref]) if counts[ref] else ''
        counts[ref] += 1
    conditions, condition_errors = project_many(raw['constraint_proposals'], project_condition, task)
    items = merge_place_mentions(items)
    supports, questions, support_errors = support_results(raw['support_observations'], task, items)
    rejected = list(dict.fromkeys(item_errors + condition_errors + support_errors))
    issues = ['ungrounded_proposal'] if rejected else []
    if assist_conditions(conditions, task):
        issues.append('condition_rule_assisted')
    return GroundedExtraction(dict(item_proposals=items, constraint_proposals=conditions,
        support_observations=supports, questions=questions), issues, rejected)


def validate_assessments(batch, task):
    ids = [assessment.message_id for assessment in batch.message_assessments]
    if len(ids) != len(set(ids)) or set(ids) != {m['id'] for m in task['recent_messages']}:
        raise ValueError('Message assessment coverage mismatch')


def project_support(proposal, task):
    from ai.extraction import validate_support
    message = source_message(proposal['evidence'], task)
    item = next((item for item in task['items'] if item['id'] == proposal['item_id']), None)
    claim = dict({k: v for k, v in proposal.items() if k != 'evidence'}, source_message_id=proposal['evidence']['message_id'])
    return validate_support(claim, message, item)[0]


def support_results(raw, task, items):
    from ai.assistance import explicit_support
    from ai.extraction import validate_extraction
    scope = dict(task, items=task['items'] + [dict(i, id=i['client_ref'], item_version=1) for i in items])
    claims, questions = explicit_support(scope, scope['items'])
    modeled, rejected = project_many(raw, project_support, scope)
    valid = validate_extraction(dict(support_observations=claims + modeled), scope)
    return valid['support_observations'], questions + valid['questions'], rejected


def assist_conditions(conditions, task):
    from ai.condition_grounding import condition_value
    from ai.extraction_schema import ConditionFact
    from ai.extraction_projection import condition_proposal
    added = 0
    for message in task['recent_messages']:
        for key in ('budget_krw', 'return_by'):
            value = condition_value(key, message['text'])
            if value is None:
                continue
            raw = condition_proposal(ConditionFact(key=key,value=value), message, task, dict(message_id=message['id'],quote=message['text']))
            proposal = project_condition(raw, task)
            if proposal and proposal not in conditions:
                conditions.append(proposal)
                added += 1
    return added


def merge_place_mentions(items):
    grouped = {}
    for item in items:
        key = item['existing_item_id'], normalized(item['title'])
        canonical = grouped.setdefault(key, item)
        canonical['source_message_ids'] = list(dict.fromkeys(canonical['source_message_ids'] + item['source_message_ids']))
    return list(grouped.values())
