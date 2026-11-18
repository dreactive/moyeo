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
