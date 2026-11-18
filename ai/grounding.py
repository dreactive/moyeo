"""Evidence checks shared by model extraction and deterministic assistance."""
from dataclasses import dataclass
import unicodedata


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
    raw = batch.model_dump()
    items, item_errors = project_many(raw['item_proposals'], project_item, task)
    conditions, condition_errors = project_many(raw['constraint_proposals'], project_condition, task)
    rejected = list(dict.fromkeys(item_errors + condition_errors))
    return GroundedExtraction(dict(item_proposals=items, constraint_proposals=conditions,
        support_observations=[], questions=[]), ['ungrounded_proposal'] if rejected else [], rejected)
