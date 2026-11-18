import pytest

from backend.db import Database
from backend.services.pipeline_store import PipelineStore


@pytest.fixture
def database(tmp_path):
    db = Database(tmp_path / 'pipeline.sqlite3')
    yield db
    db.close()


def put_room(db, room_id, *message_ids):
    messages = [
        dict(id=message_id, room_id=room_id, seq=index, author_id=room_id,
             text=f'message {message_id}')
        for index, message_id in enumerate(message_ids, 1)
    ]
    db.put('room:' + room_id, dict(room_id=room_id, messages=messages))
    return messages


def submit(store, room_id, *messages):
    return store.create(dict(room_id=room_id, goal='new_message', base_versions={'plan_revision': 0},
                             recent_messages=list(messages), user_selection=None))


def test_store_persists_immutable_job_and_run_receipt(database):
    message, = put_room(database, 'r', 'm1')
    store = PipelineStore(database)
    job = submit(store, 'r', message)
    message['text'] = 'caller mutation'
    job['task']['base_versions']['plan_revision'] = 99

    second = PipelineStore(database).jobs('r')[0]
    assert second['phase'] == 'extraction_queued'
    assert second['task']['base_versions'] == {'plan_revision': 0}
    assert second['task']['recent_messages'][0]['text'] == 'message m1'
    assert second['message_ids'] == ['m1']
    assert second['boundary_seq'] == 1
    assert second['run_id'] != second['extraction_id']
    run = database.get('run:' + second['run_id'])
    assert run['room_id'] == 'r'
    assert run['message_ids'] == ['m1']
    assert store.covered_ids('r') == {'m1'}


def test_create_rejects_foreign_reordered_and_overlapping_sources(database):
    m1, m2 = put_room(database, 'a', 'a1', 'a2')
    foreign, = put_room(database, 'b', 'b1')
    store = PipelineStore(database)
    with pytest.raises(ValueError):
        submit(store, 'a', foreign)
    with pytest.raises(ValueError):
        submit(store, 'a', m2, m1)
    submit(store, 'a', m1)
    with pytest.raises(ValueError):
        submit(store, 'a', m1, m2)
    assert store.covered_ids('a') == {'a1'}


def test_extraction_can_run_ahead_without_moving_execution_cursor(database):
    m1, m2 = put_room(database, 'r', 'm1', 'm2')
    store = PipelineStore(database)
    first = submit(store, 'r', m1)
    second = submit(store, 'r', m2)
    assert store.claim('execution') is None
    assert store.finish_extraction(store.claim('extraction'), {'prepared': 'first'})
    running = store.claim('execution')
    assert running['id'] == first['id']
    ready = store.claim('extraction')
    assert ready['id'] == second['id']
    assert store.finish_extraction(ready, {'prepared': 'second'})
    assert database.get('extracted-message:r') == 'm2'
    assert database.get('pipeline-cursors:r').get('executed_seq', 0) == 0
    assert store.claim('execution') is None

    completion = store.completion_records(running, {'phase': 'done', 'last_processed_message_id': 'm1'})
    assert store.jobs('r')[0]['phase'] == 'executing'
    assert database.get('processed-message:r') is None
    database.put_many(completion)
    assert database.get('pipeline-cursors:r') == {'extracted_seq': 2, 'executed_seq': 1}
    assert store.claim('execution')['id'] == second['id']


def test_ready_limits_keep_other_rooms_moving_and_preserve_backlog(database):
    a1, a2, a3 = put_room(database, 'a', 'a1', 'a2', 'a3')
    b1, = put_room(database, 'b', 'b1')
    c1, = put_room(database, 'c', 'c1')
    store = PipelineStore(database, ready_limit=2, per_room_ready_limit=1)
    for room_id, message in [('a', a1), ('a', a2), ('a', a3), ('b', b1), ('c', c1)]:
        submit(store, room_id, message)

    for expected in ['a1', 'b1']:
        job = store.claim('extraction')
        assert job['message_ids'] == [expected]
        assert store.finish_extraction(job, {})
    assert store.claim('extraction') is None
    assert store.counts()['extraction_queued'] == 3
    execution = store.claim('execution')
    assert execution['message_ids'] == ['a1']
    assert store.claim('extraction') is None
    database.put_many(store.completion_records(execution, 'done'))
    job = store.claim('extraction')
    assert job['message_ids'] == ['c1']


def test_retries_replace_tokens_and_bound_context_refresh(database):
    m1, = put_room(database, 'r', 'm1')
    store = PipelineStore(database)
    submit(store, 'r', m1)
    first = store.claim('extraction')
    assert store.requeue(first, 'extraction', 'timeout')
    second = store.claim('extraction')
    assert second['token'] != first['token']
    assert not store.finish_extraction(first, {'bad': True})
    assert not store.requeue(second, 'extraction', 'timeout')
    assert store.finish_extraction(second, {'version': 1})

    execution = store.claim('execution')
    assert store.requeue(execution, 'extraction', 'context_changed', revalidation=True)
    refreshed = store.claim('extraction')
    assert refreshed['prepared'] == {'version': 1}
    assert store.finish_extraction(refreshed, {'version': 2})
    execution = store.claim('execution')
    assert execution['prepared'] == {'version': 2}
    assert not store.requeue(execution, 'extraction', 'context_changed', revalidation=True)
    assert store.fail(execution, 'retry_limit')
    assert not store.completion_records(execution, 'done')
    assert store.covered_ids('r') == set()


def test_recovery_requeues_each_stage_preserving_prepared_payload(tmp_path):
    path = tmp_path / 'restart.sqlite3'
    db = Database(path)
    a1, = put_room(db, 'a', 'a1')
    b1, = put_room(db, 'b', 'b1')
    store = PipelineStore(db)
    first, second = submit(store, 'a', a1), submit(store, 'b', b1)
    assert store.finish_extraction(store.claim('extraction'), {'prepared': 'a1'})
    stale_extraction = store.claim('extraction')
    stale_execution = store.claim('execution')
    db.close()

    db = Database(path)
    try:
        store = PipelineStore(db)
        store.recover()
        extracting = store.claim('extraction')
        executing = store.claim('execution')
        assert (extracting['id'], executing['id']) == (second['id'], first['id'])
        assert extracting['token'] != stale_extraction['token']
        assert executing['token'] != stale_execution['token']
        assert executing['prepared'] == {'prepared': 'a1'}
        assert not store.finish_extraction(stale_extraction, {})
        assert not store.completion_records(stale_execution, 'done')
        store.recover()
        assert store.counts()['failed'] == 2
        assert store.claim('extraction') is store.claim('execution') is None
    finally:
        db.close()


def test_recovery_honors_applied_run_and_exact_processed_message(database):
    m1, m2 = put_room(database, 'r', 'm1', 'm2')
    store = PipelineStore(database)
    submit(store, 'r', m1, m2)
    assert store.finish_extraction(store.claim('extraction'), {})
    job = store.claim('execution')
    run_key = 'run:' + job['run_id']
    database.put_many({run_key: dict(database.get(run_key), applied=True), 'processed-message:r': 'm1'})
    store.recover()
    assert store.jobs('r')[0]['phase'] == 'done'
    assert store.claim('execution') is None
    assert database.get('pipeline-cursors:r') == {'extracted_seq': 2, 'executed_seq': 1}


def test_manual_retry_of_failed_gap_cannot_regress_cursors(database):
    m1, m2 = put_room(database, 'r', 'm1', 'm2')
    store = PipelineStore(database)
    first = submit(store, 'r', m1)
    assert store.fail(store.claim('extraction'), 'failed')
    submit(store, 'r', m2)
    assert store.finish_extraction(store.claim('extraction'), {})
    execution = store.claim('execution')
    database.put_many(store.completion_records(execution, {'phase': 'done', 'last_processed_message_id': 'm2'}))

    retry = store.create(dict(room_id='r', goal='manual_replan', base_versions={},
                              recent_messages=[m1], user_selection=None))
    assert retry['ordinal'] > first['ordinal']
    assert store.finish_extraction(store.claim('extraction'), {})
    execution = store.claim('execution')
    database.put_many(store.completion_records(execution, {'phase': 'done', 'last_processed_message_id': 'm1'}))
    assert database.get('extracted-message:r') == 'm2'
    assert database.get('pipeline-cursors:r') == {'extracted_seq': 2, 'executed_seq': 2}


def test_executing_job_checkpoints_same_call_only_and_survives_restart(database):
    m1, = put_room(database, 'r', 'm1')
    store = PipelineStore(database)
    submit(store, 'r', m1)
    assert store.finish_extraction(store.claim('extraction'), {})
    job = store.claim('execution')
    call = dict(run_id=job['run_id'], call_id=job['run_id'] + ':1', event='tool_call',
                created_at='2026-11-19T10:00:00+09:00',
                payload=dict(tool_name='search_places', arguments={'region': '여수', 'query': '공원'}))
    answer = dict(call, event='tool_result',
                  payload=dict(call['payload'], normalized_result={'places': []}, source_refs=['ref']))
    assert not store.checkpoint_call(job, answer)
    assert store.checkpoint_call(job, call)
    assert not store.checkpoint_call(job, dict(answer, run_id='foreign'))
    assert not store.checkpoint_call(job, dict(answer, payload=dict(answer['payload'], arguments={})))
    assert store.checkpoint_call(job, answer)
    assert store.checkpoint_call(job, answer)
    reopened = PipelineStore(database)
    reopened.recover()
    assert reopened.restore_observations('r') == [
        dict(tool_name='search_places', arguments={'region': '여수', 'query': '공원'},
             result={'places': []}, observed_at='2026-11-19T10:00:00+09:00', source_refs=['ref'])
    ]
    assert not reopened.restore_observations('other')
    assert not reopened.checkpoint_call(job, answer)


def test_deleted_room_ignores_late_stage_callbacks_and_clears_run_index(database):
    m1, m2 = put_room(database, 'r', 'm1', 'm2')
    store = PipelineStore(database)
    first, second = submit(store, 'r', m1), submit(store, 'r', m2)
    assert store.finish_extraction(store.claim('extraction'), {})
    execution = store.claim('execution')
    extraction = store.claim('extraction')
    database.delete_many(['room:r'])
    assert not store.finish_extraction(extraction, {})
    assert not store.completion_records(execution, 'done')
    store.purge_room('r')
    store.recover()
    assert not store.jobs('r')
    assert database.get('run:' + first['run_id']) is None
    assert database.get('run:' + second['extraction_id']) is None
    assert database.get('extracted-message:r') is None
    assert database.get('pipeline-cursors:r') is None


def test_context_refresh_can_reuse_its_reserved_prepared_slot(database):
    a1, a2, a3 = put_room(database, 'a', 'a1', 'a2', 'a3')
    b1, = put_room(database, 'b', 'b1')
    store = PipelineStore(database, ready_limit=2, per_room_ready_limit=2)
    initial = submit(store, 'a', a1)
    submit(store, 'a', a2)
    submit(store, 'a', a3)
    for _ in range(2):
        assert store.finish_extraction(store.claim('extraction'), {})
    first = store.claim('execution')
    assert store.requeue(first, 'extraction', 'context_changed', revalidation=True)

    submit(store, 'b', b1)
    refresh = store.claim('extraction')
    assert refresh['id'] == initial['id']
    assert store.finish_extraction(refresh, {})
    assert store.claim('extraction') is None
    assert store.counts()['execution_queued'] == 2


def test_claim_checks_forged_run_identity_before_persisting_extraction(database):
    message, = put_room(database, 'r', 'm1')
    store = PipelineStore(database)
    submit(store, 'r', message)
    extraction = store.claim('extraction')

    assert not store.finish_extraction(dict(extraction, run_id='forged'), {'forged': True})
    assert store.finish_extraction(extraction, {'valid': True})
    assert store.claim('execution')['prepared'] == {'valid': True}


def test_checkpoint_restores_arguments_from_actual_result_event_shape(database):
    message, = put_room(database, 'r', 'm1')
    store = PipelineStore(database)
    submit(store, 'r', message)
    assert store.finish_extraction(store.claim('extraction'), {})
    job = store.claim('execution')
    event = dict(run_id=job['run_id'], call_id=job['run_id'] + ':1', step=1,
                 created_at='2026-11-19T01:00:00+00:00')
    args = {'place_ref': 'place-1'}
    assert store.checkpoint_call(job, dict(event, event='tool_call',
                                          payload=dict(tool_name='get_place_details', arguments=args,
                                                       selection_origin='qwen_argmax')))
    result = {'place': {'id': 'place-1'}, 'evidence': [{'id': 'evidence-1'}]}
    assert store.checkpoint_call(job, dict(event, event='tool_result',
                                          payload=dict(tool_name='get_place_details', normalized_result=result,
                                                       source_refs=['evidence-1'], execution_source='http',
                                                       duration_ms=25)))
    assert store.restore_observations('r') == [
        dict(tool_name='get_place_details', arguments=args, result=result,
             source_refs=['evidence-1'], observed_at=event['created_at'])
    ]
