"""Persist failed extraction receipts separately from the advancing message cursor."""
from backend.db import serialized


def select_extraction_messages(messages, processed_id, failures, retry_failed=False):
    start = next((index + 1 for index, message in enumerate(messages) if message['id'] == processed_id), 0)
    return [message for index, message in enumerate(messages)
            if (failures.get(message['id'], {}).get('status') == 'retry_required' and retry_failed)
            or index >= start and failures.get(message['id'], {}).get('status') != 'retry_required'][:20]
