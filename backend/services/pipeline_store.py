"""Durable scheduling and stage receipts for the two agent workers."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
from uuid import uuid4


JOB_PREFIX = 'pipeline-job:'
PHASES = ('received', 'extraction_queued', 'extracting', 'execution_queued', 'executing',
          'done', 'held', 'failed')
TERMINAL = {'done', 'held', 'failed'}
READY = {'execution_queued', 'executing'}
STAGES = {
    'extraction': ('extraction_queued', 'extracting', 'extraction_attempts'),
    'execution': ('execution_queued', 'executing', 'execution_attempts'),
}
READ_TOOLS = {'search_places', 'get_place_details', 'get_car_route'}


def now():
    return datetime.now(timezone.utc).isoformat()


def job_key(job):
    return f"{JOB_PREFIX}{job['room_id']}:{job['ordinal']:016d}"


def transition(job, phase, *, token=None):
    job.update(phase=phase, token=token)
    job['timestamps'][phase] = now()


def call_signature(name, arguments):
    return name, json.dumps(arguments, sort_keys=True, separators=(',', ':'))


class PipelineStore:
    def __init__(self, db, *, max_attempts=2, ready_limit=64, per_room_ready_limit=8):
        if min(max_attempts, ready_limit, per_room_ready_limit) < 1:
            raise ValueError('Pipeline limits must be positive')
        self.db = db
        self.max_attempts = max_attempts
        self.ready_limit = ready_limit
        self.per_room_ready_limit = per_room_ready_limit
        self.last_room = dict.fromkeys(STAGES)

    def jobs(self, room_id=None):
        prefix = JOB_PREFIX if room_id is None else f'{JOB_PREFIX}{room_id}:'
        return [job for _, job in self.db.scan(prefix)]

    def covered_ids(self, room_id):
        return {message_id for job in self.jobs(room_id) if job['phase'] not in ('held', 'failed')
                for message_id in job['message_ids']}

    def counts(self, room_id=None):
        counts = Counter(job['phase'] for job in self.jobs(room_id))
        return {phase: counts[phase] for phase in PHASES}

    def create(self, task):
        room_id = task['room_id']
        with self.db.lock:
            room = self.db.get('room:' + room_id)
            if room is None:
                raise ValueError('Room not found')
            messages = task.get('recent_messages', [])
            ids = [message['id'] for message in messages]
            sources = {message['id']: (index, message)
                       for index, message in enumerate(room['messages'], 1)}
            positions = [sources.get(message_id, (0, None))[0] for message_id in ids]
            if (len(ids) > 20 or positions != sorted(set(positions))
                    or any(message.get('room_id') != room_id
                           or message != sources.get(message['id'], (0, None))[1]
                           for message in messages)):
                raise ValueError('Invalid reserved message range')
            existing = self.jobs(room_id)
            covered = {message_id for job in existing if job['phase'] not in ('held', 'failed')
                       for message_id in job['message_ids']}
            if set(ids) & covered:
                raise ValueError('Message already has a pipeline job')
            ordinal = existing[-1]['ordinal'] + 1 if existing else 1
            run_id = task.get('run_id') or uuid4().hex
            if self.db.get('run:' + run_id) is not None:
                raise ValueError('Run ID is already registered')
            extraction_id = uuid4().hex
            task = dict(deepcopy(task), run_id=run_id)
            job = dict(id=uuid4().hex, run_id=run_id, extraction_id=extraction_id,
                       room_id=room_id, ordinal=ordinal, task=task, message_ids=ids,
                       boundary_seq=positions[-1] if positions else len(room['messages']), extraction_attempts=0,
                       execution_attempts=0, revalidation_count=0, revalidation_pending=False,
                       revalidation_started=False, prepared=None, timestamps={'received': now()},
                       tool_receipts={}, outcome=None)
            transition(job, 'extraction_queued')
            run = dict(room_id=room_id, base_versions=task['base_versions'], message_ids=ids,
                       job_id=job['id'], extraction_id=extraction_id)
            self.db.put_many({job_key(job): job, 'run:' + run_id: run,
                              'run:' + extraction_id: dict(run, run_id=run_id, stage='extraction')})
            return job

    def claim(self, stage):
        queued, active, attempts = STAGES[stage]
        with self.db.lock:
            jobs = self.jobs()
            if any(job['phase'] == active for job in jobs):
                return None
            # A context refresh temporarily leaves the execution queue but keeps its slot.
            ready = Counter(job['room_id'] for job in jobs
                            if job['phase'] in READY or job['revalidation_pending'])
            has_global_capacity = sum(ready.values()) < self.ready_limit
            heads = {}
            for job in jobs:
                phase = job['phase']
                if phase in TERMINAL or stage == 'extraction' and phase in READY:
                    continue
                heads.setdefault(job['room_id'], job)
            eligible = {room_id: job for room_id, job in heads.items()
                        if job['phase'] == queued
                        and (stage == 'execution' or job['revalidation_pending']
                             or has_global_capacity and ready[room_id] < self.per_room_ready_limit)
                        and self.db.get('room:' + room_id) is not None}
            if not eligible:
                return None
            previous = self.last_room[stage]
            if previous is None:
                room_id = min(eligible, key=lambda room_id: eligible[room_id]['timestamps']['received'])
            else:
                room_id = min(eligible, key=lambda room_id: (room_id <= previous, room_id))
            job = eligible[room_id]
            if stage == 'extraction' and job['revalidation_pending']:
                job['revalidation_started'] = True
            else:
                job[attempts] += 1
            transition(job, active, token=uuid4().hex)
            self.db.put(job_key(job), job)
            self.last_room[stage] = room_id
            return job

    def _active(self, claim, phase=None):
        job = self.db.get(job_key(claim))
        if (job is None or job['id'] != claim['id'] or job['run_id'] != claim['run_id']
                or job['extraction_id'] != claim['extraction_id'] or job['token'] is None
                or job['token'] != claim['token']
                or job['phase'] not in ('extracting', 'executing')
                or phase is not None and job['phase'] != phase):
            return None, None
        room = self.db.get('room:' + job['room_id'])
        return (job, room) if room is not None else (None, None)

    def _cursor_records(self, job, room, message_id, cursor):
        if message_id not in job['message_ids']:
            return {}
        cursor_key = 'pipeline-cursors:' + job['room_id']
        cursors = self.db.get(cursor_key) or {'extracted_seq': 0, 'executed_seq': 0}
        seq = next((seq for seq, message in enumerate(room['messages'], 1) if message['id'] == message_id), 0)
        if seq <= cursors[cursor]:
            return {}
        cursors[cursor] = seq
        records = {cursor_key: cursors}
        if cursor == 'extracted_seq':
            records['extracted-message:' + job['room_id']] = message_id
        return records

    def finish_extraction(self, job, prepared):
        with self.db.lock:
            current, room = self._active(job, 'extracting')
            if current is None:
                return False
            current.update(prepared=prepared, revalidation_pending=False)
            transition(current, 'execution_queued')
            message_ids = current['message_ids']
            records = self._cursor_records(current, room, message_ids[-1] if message_ids else None,
                                           'extracted_seq')
            records[job_key(current)] = current
            self.db.put_many(records)
            return True

    def _can_retry(self, job, stage):
        if stage == 'extraction' and job['revalidation_pending']:
            return not job['revalidation_started']
        return job[STAGES[stage][2]] < self.max_attempts

    def requeue(self, job, stage, reason, *, revalidation=False):
        queued, active, _ = STAGES[stage]
        expected = 'executing' if revalidation else active
        with self.db.lock:
            current, _ = self._active(job, expected)
            if current is None:
                return False
            if revalidation:
                if stage != 'extraction' or current['revalidation_count']:
                    return False
                current.update(revalidation_count=1, revalidation_pending=True,
                               revalidation_started=False)
                # The rejected input never entered the execution stage.
                current['execution_attempts'] -= 1
            elif not self._can_retry(current, stage):
                return False
            current['last_error'] = reason
            transition(current, queued)
            self.db.put(job_key(current), current)
            return True

    def fail(self, job, reason):
        with self.db.lock:
            current, _ = self._active(job)
            if current is None:
                return False
            self.db.put_many(self._terminal_records(current, {'phase': 'failed', 'reason': reason}))
            return True

    def _terminal_records(self, job, outcome):
        job.update(outcome=outcome, revalidation_pending=False)
        transition(job, outcome['phase'])
        return {job_key(job): job}

    def completion_records(self, job, outcome):
        """Return records for the caller to commit with the apply fence under db.lock."""
        outcome = {'phase': outcome} if isinstance(outcome, str) else deepcopy(outcome)
        if outcome['phase'] not in TERMINAL:
            raise ValueError('Invalid phase for pipeline completion')
        with self.db.lock:
            current, room = self._active(job, 'executing')
            if current is None:
                return {}
            records = self._terminal_records(current, outcome)
            records.update(self._cursor_records(current, room, outcome.get('last_processed_message_id'),
                                                'executed_seq'))
            return records

    def checkpoint_call(self, job, event):
        with self.db.lock:
            current, _ = self._active(job, 'executing')
            call_id = event.get('call_id')
            if (current is None or event.get('run_id') != current['run_id']
                    or not isinstance(call_id, str) or not call_id.startswith(current['run_id'] + ':')
                    or event.get('room_id') not in (None, current['room_id'])):
                return False
            payload = event.get('payload', {})
            name, arguments = payload.get('tool_name'), payload.get('arguments')
            if name not in READ_TOOLS:
                return False
            key = f"{current['token']}:{call_id}"
            receipts = current['tool_receipts']
            receipt = receipts.get(key)
            if event.get('event') == 'tool_call':
                if not isinstance(arguments, dict):
                    return False
                if receipt is not None:
                    return call_signature(name, arguments) == call_signature(receipt['tool_name'], receipt['arguments'])
                receipts[key] = dict(call_id=call_id, tool_name=name,
                                     arguments=arguments, started_at=event['created_at'])
            elif event.get('event') == 'tool_result':
                result = payload.get('normalized_result')
                if (receipt is None or name != receipt['tool_name'] or payload.get('failed')
                        or not isinstance(result, dict)):
                    return False
                if ('arguments' in payload and (not isinstance(arguments, dict)
                        or call_signature(name, arguments) != call_signature(name, receipt['arguments']))):
                    return False
                if 'result' in receipt:
                    return json.dumps(receipt['result'], sort_keys=True) == json.dumps(result, sort_keys=True)
                receipt.update(result=result, observed_at=event['created_at'],
                               source_refs=payload.get('source_refs', []))
            else:
                return False
            self.db.put(job_key(current), current)
            return True

    def restore_observations(self, room_id):
        with self.db.lock:
            if self.db.get('room:' + room_id) is None:
                return []
            observations = {}
            receipts = [receipt for job in self.jobs(room_id) for receipt in job['tool_receipts'].values()
                        if 'result' in receipt]
            for receipt in sorted(receipts, key=lambda value: value['observed_at']):
                signature = call_signature(receipt['tool_name'], receipt['arguments'])
                observations[signature] = {key: receipt[key] for key in ('tool_name', 'arguments',
                                                                        'result', 'observed_at', 'source_refs')}
            return list(observations.values())

    def recover(self):
        summary = dict(requeued=0, failed=0, applied=0, purged=0)
        with self.db.lock:
            jobs = self.jobs()
            orphan_rooms = {job['room_id'] for job in jobs
                            if self.db.get('room:' + job['room_id']) is None}
            for room_id in orphan_rooms:
                self.purge_room(room_id)
                summary['purged'] += 1
            for job in jobs:
                room_id, phase = job['room_id'], job['phase']
                if room_id in orphan_rooms or phase in TERMINAL:
                    continue
                run = self.db.get('run:' + job['run_id'])
                if run and run.get('applied'):
                    records = self._terminal_records(job, {'phase': 'done', 'reason': 'already_applied'})
                    records.update(self._cursor_records(job, self.db.get('room:' + room_id),
                                                        self.db.get('processed-message:' + room_id),
                                                        'executed_seq'))
                    self.db.put_many(records)
                    summary['applied'] += 1
                elif phase in ('extracting', 'executing'):
                    stage = 'extraction' if phase == 'extracting' else 'execution'
                    if self._can_retry(job, stage):
                        transition(job, STAGES[stage][0])
                        self.db.put(job_key(job), job)
                        summary['requeued'] += 1
                    else:
                        self.fail(job, 'interrupted_at_attempt_limit')
                        summary['failed'] += 1
                elif phase == 'received':
                    transition(job, 'extraction_queued')
                    self.db.put(job_key(job), job)
                    summary['requeued'] += 1
        return summary

    def purge_room(self, room_id):
        with self.db.lock:
            jobs = self.jobs(room_id)
            keys = [f'extracted-message:{room_id}', f'pipeline-cursors:{room_id}']
            for job in jobs:
                keys.extend((job_key(job), 'run:' + job['run_id'], 'run:' + job['extraction_id']))
            self.db.delete_many(keys)
