"""Controlled comparison of the serial and staged room pipelines."""
import asyncio
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
from threading import Lock
from time import perf_counter, sleep

from ai.models.worker import ModelWorker
from ai.tests.test_auxiliary import analysis, batch, evidence
from ai.tests.test_judged_runner import Judge
from ai.tools.registry import RegisteredTools
from backend.adapters.local_ai import LocalAIBridge
from backend.db import Database
from backend.services.agent_jobs import AgentJobs
from backend.services.messages import save_message
from backend.tests.test_pipeline_runtime import ROOM_ID, lookup, seed_room, stop


LOOKUP_TEXT = '가상 B공원 찾아줘. 내 예산은 15만원이야.'
CORRECTION_TEXT = '내 예산은 20만원이야.'
TAGS = {LOOKUP_TEXT: 'lookup', CORRECTION_TEXT: 'correction'}


class Probe:
    def __init__(self):
        self.started = perf_counter()
        self.events = []
        self.tool_entered = asyncio.Event()
        self.release_tool = asyncio.Event()
        self.correction_prepared = asyncio.Event()
        self.lock = Lock()
        self.judging = self.judge_peak = 0

    def note(self, event, **data):
        with self.lock:
            self.events.append(dict(event=event, ms=round((perf_counter() - self.started) * 1000, 3), **data))

    def extract(self, task, stage=1):
        tags = [TAGS[m['text']] for m in task['recent_messages']]
        self.note('aux_start', tags=tags, stage=stage)
        sleep(0.005)
        requests, constraints = [], []
        for message in task['recent_messages']:
            initial = message['text'] == LOOKUP_TEXT
            quote = '내 예산은 15만원이야' if initial else CORRECTION_TEXT.rstrip('.')
            constraints.append(dict(key='budget_krw', value=150000 if initial else 200000,
                                    evidence=evidence(quote, message['id'])))
            if initial:
                requests.append(lookup(message, target='가상 B공원'))
        self.note('aux_end', tags=tags, stage=stage)
        return batch(constraint_proposals=constraints, analysis=analysis(requests=requests))


class MeasuredJudge(Judge):
    def __init__(self, probe):
        super().__init__()
        self.probe = probe

    def score_candidates(self, context, candidates):
        with self.probe.lock:
            self.probe.judging += 1
            self.probe.judge_peak = max(self.probe.judge_peak, self.probe.judging)
        self.probe.note('judge_start')
        try:
            sleep(0.002)
            return super().score_candidates(context, candidates)
        finally:
            self.probe.note('judge_end')
            with self.probe.lock:
                self.probe.judging -= 1


class PreparedBridge(LocalAIBridge):
    def __init__(self, probe):
        super().__init__(dict(model_backend='fake', provider_mode='fixture', max_decision_rounds=4))
        self.probe = probe

    async def start(self):
        await super().start()
        self.runtime.auxiliary = self.probe
        self.runtime.model = ModelWorker(MeasuredJudge(self.probe))

    async def extract(self, task, previous=None):
        prepared = await super().extract(task, previous)
        tags = [TAGS[m['text']] for m in task['recent_messages']]
        self.probe.note('prepared', tags=tags)
        if 'correction' in tags:
            self.probe.correction_prepared.set()
        return prepared


class SerialPort:
    """Exercise AgentJobs' original run-only worker using the same runtime."""
    def __init__(self, bridge):
        self.bridge = bridge

    async def run(self, task, emit_trace):
        return await self.bridge.run(task, emit_trace)

    async def run_current(self, task, emit_trace, is_current):
        return await self.bridge.run_current(task, emit_trace, is_current)


def find_event(events, event, *, tag=None):
    return next(i for i, row in enumerate(events)
                if row['event'] == event and (tag is None or tag in row.get('tags', [])))


def measurement(probe):
    events = probe.events
    waits = {}
    for tag in TAGS.values():
        enqueued = events[find_event(events, 'enqueue', tag=tag)]
        started = events[find_event(events, 'aux_start', tag=tag)]
        waits[tag] = round(started['ms'] - enqueued['ms'], 3)
    durations = {}
    for phase in ('aux', 'judge', 'tool'):
        starts = [row['ms'] for row in events if row['event'] == phase + '_start']
        ends = [row['ms'] for row in events if row['event'] == phase + '_end']
        durations[phase] = [round(end - start, 3) for start, end in zip(starts, ends)]
    return dict(elapsed_ms=events[-1]['ms'], queue_to_aux_ms=waits, duration_samples_ms=durations,
                judge_peak=probe.judge_peak, events=events)


def test_per_message_serial_burst_serial_and_burst_staged_preserve_final_meaning(room, monkeypatch):
    fixture_execute = RegisteredTools.execute

    async def run_case(case):
        probe = Probe()
        bridge = PreparedBridge(probe)
        await bridge.start()

        async def observed_execute(tools, name, arguments):
            first_read = name == 'search_places' and not probe.tool_entered.is_set()
            probe.note('tool_start', name=name, arguments=deepcopy(arguments))
            if first_read:
                probe.tool_entered.set()
                await probe.release_tool.wait()
            await asyncio.sleep(0.005)
            answer = await fixture_execute(tools, name, arguments)
            probe.note('tool_end', name=name)
            return answer

        monkeypatch.setattr(RegisteredTools, 'execute', observed_execute)
        with closing(Database(':memory:')) as db:
            seed_room(db, room)
            jobs = AgentJobs(db, bridge if case == 'staged_burst' else SerialPort(bridge))
            worker = asyncio.create_task(jobs.work())

            async def submit(text):
                probe.note('enqueue', tags=[TAGS[text]])
                message = save_message(db, ROOM_ID, 'u1', text)
                receipt = await jobs.enqueue(ROOM_ID, 'new_message')
                return message['id'], receipt['run_id']

            try:
                first, first_run = await submit(LOOKUP_TEXT)
                await asyncio.wait_for(probe.tool_entered.wait(), 2)
                if case == 'serial_per_message':
                    probe.release_tool.set()
                    await asyncio.wait_for(jobs.queue.join(), 5)
                    assert db.get('processed-message:' + ROOM_ID) == first
                second, _ = await submit(CORRECTION_TEXT)
                if case == 'staged_burst':
                    await asyncio.wait_for(probe.correction_prepared.wait(), 2)
                    assert db.get('processed-message:' + ROOM_ID) is None
                probe.release_tool.set()
                await asyncio.wait_for(jobs.queue.join(), 5)
                probe.note('drained')

                saved = db.get('room:' + ROOM_ID)
                assert db.get('processed-message:' + ROOM_ID) == second
                assert saved['current_plan'] is None
                sources = {first: 'lookup', second: 'correction'}
                constraints = [(c['owner_id'], c['value'], c['status'], [sources[mid] for mid in c['source_message_ids']])
                               for c in saved['constraints']]
                requests = [(r['owner_id'], r['status'], r['target_names'], sources[r['source_message_id']])
                            for r in saved['agent_requests']]
                original_events = db.traces[first_run]['events']
                applied = bool(db.get('run:' + first_run).get('applied'))
                if case == 'serial_burst':
                    assert not applied
                    assert any(e['event'] == 'state_applied' and not e['payload']['applied'] for e in original_events)
                elif case == 'staged_burst':
                    assert applied
                    deferred, = [job for job in jobs.pipeline.store.jobs(ROOM_ID) if job['run_id'] == first_run]
                    assert deferred['outcome']['reason'] == 'deferred_to_newer_input'
                    assert any(e['event'] == 'execution' and e['payload']['state'] == 'stale' for e in original_events)
                else:
                    assert applied
                return dict(constraints=constraints, requests=requests, original_run_applied=applied,
                            search_calls=sum(e['event'] == 'tool_start' and e['name'] == 'search_places' for e in probe.events),
                            **measurement(probe))
            finally:
                probe.release_tool.set()
                await stop(worker)
                await bridge.aclose()

    async def compare():
        return {case: await run_case(case) for case in ('serial_per_message', 'serial_burst', 'staged_burst')}

    report = asyncio.run(compare())
    expected_constraints = [('u1', 150000, 'needs_owner_confirmation', ['lookup']), ('u1', 200000, 'needs_owner_confirmation', ['correction'])]
    expected_requests = [('u1', 'completed', ['가상 B공원'], 'lookup')]
    for case, result in report.items():
        assert result['constraints'] == expected_constraints, case
        assert result['requests'] == expected_requests, case
        assert result['judge_peak'] == 1, case
        events = result['events']
        correction = find_event(events, 'aux_start', tag='correction')
        if case == 'staged_burst':
            prepared = find_event(events, 'prepared', tag='correction')
            assert find_event(events, 'tool_start') < correction < prepared < find_event(events, 'tool_end')
        else:
            assert find_event(events, 'tool_end') < correction
    assert [r['search_calls'] for r in report.values()] == [1, 2, 1]
    assert [[e['tags'] for e in r['events'] if e['event'] == 'aux_start'] for r in report.values()] == [
        [['lookup'], ['correction']], [['lookup'], ['lookup', 'correction']], [['lookup'], ['correction']],
    ]

    output_path = os.environ.get('CODEX_PIPELINE_COMPARISON_OUT')
    if output_path:
        artifact = dict(note='Fixture delays only. Event order is causal evidence. Elapsed time is informational.',
                        conditions=report)
        Path(output_path).write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
