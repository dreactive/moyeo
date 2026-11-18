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


def extraction_label(result):
    report = result.get('extraction_report', {})
    status = report.get('status')
    issues = set(report.get('issue_codes', []))
    if status == 'failed':
        if issues & {'auxiliary_configuration_missing', 'auxiliary_configuration_error', 'missing_credentials'}:
            return '보조 모델 API 키 또는 연결 설정이 필요합니다.'
        if 'auxiliary_request_failed' in issues:
            return '보조 모델 요청에 실패했습니다. 연결 설정을 확인하고 다시 시도해 주세요.'
        return '메시지 형식을 확인하지 못했습니다. 다시 시도해 주세요.'
    decision = result.get('decision_report', {})
    if decision.get('status') == 'stale':
        return '요청이 변경되어 선택을 보류했습니다. 새 요청을 다시 확인합니다.'
    if decision.get('status') == 'failed':
        if decision.get('reason') == 'tool_failed':
            return '선택한 도구 실행에 실패했습니다. 다시 시도해 주세요.'
        return 'Qwen 후보 채점에 실패해 실행을 보류했습니다. 다시 시도해 주세요.'
    if decision.get('action') == 'ask' or decision.get('reason') == 'selection_needs_input':
        question = next((q['text'] for q in result.get('questions', []) if q.get('text')), None)
        if question:
            return question
    if decision.get('action') in ('direct', 'unsupported') and result.get('response'):
        return result['response']
    if result.get('observations') and result['completion'] == 'needs_input':
        return '도구 실행은 완료됐으며 후속 작업에 필요한 정보 보완이 남았습니다.'
    if status == 'filtered':
        return '근거를 확인하지 못한 제안은 반영하지 않았습니다.'
    return {'done': '처리를 마쳤습니다.', 'needs_input': '작업에 필요한 정보를 확인해 주세요.',
            'unsupported': '현재 도구로 요청을 수행할 수 없습니다.'}.get(result['completion'], result['completion'])
