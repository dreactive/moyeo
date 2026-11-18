"""Persist failed extraction receipts separately from the advancing message cursor."""
from backend.db import serialized


def select_extraction_messages(messages, processed_id, failures, retry_failed=False):
    start = next((index + 1 for index, message in enumerate(messages) if message['id'] == processed_id), 0)
    return [message for index, message in enumerate(messages)
            if (failures.get(message['id'], {}).get('status') == 'retry_required' and retry_failed)
            or index >= start and failures.get(message['id'], {}).get('status') != 'retry_required'][:20]


def record_extraction_failure(db, result):
    room_id = result['room_id']
    run = db.get('run:' + result['run_id'])
    report = result['extraction_report']
    failures = db.get('failed-extraction:' + room_id) or {}
    for message_id in run.get('message_ids', []):
        failures[message_id] = dict(issue_codes=report['issue_codes'], attempts=report['attempts'], run_id=result['run_id'], status='retry_required')
    run['extraction_report'] = report
    db.put_many({'failed-extraction:' + room_id: failures, 'run:' + result['run_id']: run})


def latest_processed(messages, current, proposed):
    positions = {message['id']: index for index, message in enumerate(messages)}
    return max((current, proposed), key=lambda message_id: positions.get(message_id, -1))


def recovered_failures(failures, message_ids, processed):
    for message_id in message_ids[:message_ids.index(processed) + 1]:
        if message_id in failures:
            failures[message_id]['status'] = 'recovered'
    return failures
