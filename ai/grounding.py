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
