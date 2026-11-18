"""One durable extraction worker and one guarded Qwen/tool worker.

SQLite holds jobs and stage artifacts. Events are bounded wakeups, never the
source of truth. The serial fixture-port adapter remains in agent_jobs.py.
"""
import asyncio
from contextlib import suppress
from copy import deepcopy
from datetime import datetime, timezone
from time import perf_counter
from uuid import uuid4
from fastapi import HTTPException
from backend.services.agent_apply import apply_agent_result
from backend.services.agent_requests import TERMINAL_REQUESTS
from backend.services.extraction import select_extraction_messages, extraction_label
from backend.services.events import publish_event
from backend.services.observations import get_observations, project_observations
from backend.services.pipeline_store import PipelineStore, job_key
from backend.services.traces import store_trace

TERMINAL = {"done", "held", "failed", "cancelled"}
MESSAGE_GOALS = {"new_message", "message_created", "remaining_messages", "startup_recovery"}


def now():
    return datetime.now(timezone.utc).isoformat()


def execution_trace_fields(job):
    # A rejected context refresh returns its execution budget slot but remains
    # a distinct trace attempt. The claim token stays private to the store.
    attempt = job["execution_attempts"] + job["revalidation_count"]
    return dict(execution_id=f"{job['run_id']}:execution:{attempt}", attempt=attempt)


class DrainQueue:
    """Compatibility surface: join waits for both durable stages, not aux only."""
    def __init__(self, owner):
        self.owner = owner
    async def join(self):
        await asyncio.sleep(0)
        await self.owner.started.wait()
        while True:
            self.owner.changed.clear()
            if not self.owner.active and self.empty():
                return
            await self.owner.changed.wait()
    def qsize(self):
        return sum(j["phase"] not in TERMINAL for j in self.owner.store.jobs())
    def empty(self):
        return self.qsize() == 0
    def get_nowait(self):
        candidates = [j for j in self.owner.store.jobs() if j["phase"] not in TERMINAL]
        if not candidates:
            raise asyncio.QueueEmpty
        return deepcopy(candidates[0]["task"])


class PipelineJobs:
    def __init__(self, db, port):
        self.db, self.port = db, port
        self.store = PipelineStore(db)
        self.queue = DrainQueue(self)
        self.started = asyncio.Event()
        self.changed = asyncio.Event()
        self.wake = {stage: asyncio.Event() for stage in ("extraction", "execution")}
        self.active = {}
        self.extraction_timeout = 120
        self.execution_timeout = 300

    def notify(self):
        self.changed.set()
        for event in self.wake.values():
            event.set()

    def _room(self, room_id):
        room = self.db.get("room:" + room_id)
        if room is None:
            raise HTTPException(404, "Room not found")
        return room

    def _task(self, room, run_id, reason, selection, sources):
        from backend.services.agent_jobs import make_task
        task = make_task(room, run_id, reason, get_observations(self.db, room["room_id"]), selection,
                         self.db.get("processed-message:" + room["room_id"]),
                         self.db.get("failed-extraction:" + room["room_id"]))
        task["recent_messages"] = deepcopy(sources)
        positions = {m["id"]: i for i, m in enumerate(room["messages"])}
        start = min((positions[m["id"]] for m in sources), default=len(room["messages"]))
        task["conversation_context"] = deepcopy(room["messages"][max(0,start-20):start])
        return task

    async def enqueue(self, room_id, reason, selection=None, *, resume_ids=None, resume_items=None, parents=None, depth=0):
        with self.db.lock:
            room = self._room(room_id)
            receipts = self.store.jobs(room_id)
            known = {mid for job in receipts for mid in job["message_ids"]}
            covered = self.store.covered_ids(room_id) if reason == "manual_replan" else known
            eligible_ids = {m["id"] for m in select_extraction_messages(
                room["messages"], self.db.get("processed-message:" + room_id),
                self.db.get("failed-extraction:" + room_id) or {}, reason == "manual_replan", limit=None)}
            if reason == "manual_replan":
                eligible_ids.update(known - covered)
            eligible_ids -= covered
            eligible = [m for m in room["messages"] if m["id"] in eligible_ids]
            if reason == "continue_pending":
                eligible = []
            jobs = []
            if reason in MESSAGE_GOALS and not eligible:
                existing = [j for j in self.store.jobs(room_id) if j["phase"] not in TERMINAL]
                if existing:
                    job = existing[-1]
                    return {"run_id":job["run_id"],"base_versions":job["task"]["base_versions"]}
                return {"run_id":None,"base_versions":deepcopy(room["versions"])}
            batches = [eligible[i:i+20] for i in range(0,len(eligible),20)] if eligible else [[]]
            for sources in batches:
                task = self._task(room, uuid4().hex, reason, selection, sources)
                task["_continuation_depth"] = depth
                if resume_ids is not None:
                    task["_resume_request_ids"] = list(resume_ids)
                if resume_items is not None:
                    task["_resume_item_ids"] = list(resume_items)
                if parents:
                    task["_deferred_parent_ids"] = list(parents)
                jobs.append(self.store.create(task))
        self.notify()
        self._progress(room_id)
        first=jobs[0]
        return {"run_id":first["run_id"],"base_versions":first["task"]["base_versions"]}

    async def reconcile(self, *, startup=False):
        """Recover the save-message/enqueue crash gap without replaying failed jobs."""
        for _, room in self.db.scan("room:"):
            if not isinstance(room, dict) or "messages" not in room:
                continue
            rid = room["room_id"]
            known = {mid for job in self.store.jobs(rid) for mid in job.get("message_ids",[])}
            failures = self.db.get("failed-extraction:" + rid) or {}
            remaining = select_extraction_messages(room["messages"], self.db.get("processed-message:"+rid), failures, limit=None)
            unseen = [m for m in remaining if m["id"] not in known]
            if unseen:
                # enqueue reserves the first bounded prefix; later gaps are caught
                # after each completion, while terminal failures remain receipts.
                await self.enqueue(rid,"startup_recovery")
            if startup:
                self._restore_observations(rid)
            await self._resume_deferred(rid)
            if startup and self.store.jobs(rid):
                self._progress(rid)

    def _restore_observations(self, room_id):
        if self.db.get("room:" + room_id) is not None:
            observations = self.store.restore_observations(room_id)
            if observations:
                project_observations(self.db, room_id, observations)

    def _outstanding_sources(self, room, jobs):
        """A higher legacy cursor cannot cover a failed durable source receipt."""
        rid = room["room_id"]
        failures = self.db.get("failed-extraction:" + rid) or {}
        unresolved = {m["id"] for m in select_extraction_messages(
            room["messages"], self.db.get("processed-message:" + rid), failures,
            retry_failed=True, limit=None)}
        unresolved.update(mid for job in jobs for mid in job["message_ids"])
        for job in jobs:
            if job["phase"] == "done":
                outcome = job.get("outcome") or {}
                processed = outcome.get("last_processed_message_id")
                ids = job["message_ids"]
                if processed in ids:
                    unresolved.difference_update(ids[:ids.index(processed) + 1])
                elif outcome.get("reason") == "already_applied":
                    unresolved.difference_update(ids)
        return unresolved

    def _fresh(self, job):
        room = self._room(job["room_id"])
        original = job["task"]
        if original.get("user_selection") and original["user_selection"]["base_versions"] != room["versions"]:
            raise ValueError("Conflict selection expired")
        by_id = {m["id"]:m for m in room["messages"]}
        sources = [by_id[mid] for mid in job["message_ids"] if mid in by_id]
        if len(sources) != len(job["message_ids"]):
            raise ValueError("Reserved source disappeared")
        old = {m["id"]:m for m in original["recent_messages"]}
        for source in sources:
            if any(source.get(k)!=old[source["id"]].get(k) for k in ("id","author_id","seq","text","room_id")):
                raise ValueError("Reserved source changed")
        task = self._task(room, job["run_id"], job["task"]["goal"], original.get("user_selection"), sources)
        for key in ("_resume_request_ids","_resume_item_ids","_deferred_parent_ids","_continuation_depth"):
            if key in original:
                task[key] = deepcopy(original[key])
        if "_resume_request_ids" in task:
            # Matching a cancellation requires every potential target, even
            # when this continuation may execute only a subset of requests.
            task["_cancel_scopes"] = task["pending_requests"]
            targets = set(task["_resume_request_ids"])
            task["pending_requests"] = [r for r in task["pending_requests"]
                                        if r["request_id"] in targets or r.get("operation") == "cancel"]
        if "_resume_item_ids" in task:
            task["pending_item_ids"] = [ref for ref in task["pending_item_ids"] if ref in task["_resume_item_ids"]]
        if sources and task["goal"] == "manual_replan":
            # Chronology metadata only. Later messages never enter the model's
            # reserved source window or authorize another application of facts.
            relevant = {r["source_message_id"] for r in task["request_history"]}
            relevant.update(job["message_ids"])
            task["_request_source_order"] = {m["id"]: i for i, m in enumerate(room["messages"])
                                             if m["id"] in relevant}
        if sources:
            task["_defer_execution"] = job["boundary_seq"] < len(room["messages"])
        else:
            outstanding = self._outstanding_sources(room, self.store.jobs(room["room_id"]))
            task["_defer_execution"] = bool(outstanding)
        return task

    def _progress(self, room_id):
        with self.db.lock:
            room = self.db.get("room:"+room_id)
            if room is None:
                return
            jobs=self.store.jobs(room_id)
            data=dict(counts=self.store.counts(room_id),extraction_job_id=next((j["id"] for j in jobs if j["phase"]=="extracting"),None),
                      execution_job_id=next((j["id"] for j in jobs if j["phase"]=="executing"),None),
                      cursors=self.db.get("pipeline-cursors:"+room_id) or {})
            waiting=[j for j in jobs if j["phase"] not in TERMINAL]
            if waiting and not data["execution_job_id"]:
                extracting=next((j for j in waiting if j["phase"]=="extracting"),None)
                phase="extracting" if extracting else "execution_queued" if any(j["phase"]=="execution_queued" for j in waiting) else "extraction_queued"
                status=dict(run_id=(extracting or waiting[0])["run_id"],state="running",phase=phase,
                            label={"extracting":"새 발화를 해석하고 있습니다.","execution_queued":"해석을 마치고 실행 순서를 기다립니다.","extraction_queued":"발화 해석 순서를 기다립니다."}[phase])
            elif jobs and not waiting:
                latest = jobs[-1]
                outcome = latest.get("outcome") or {}
                status = outcome.get("public_status")
                if status is None:
                    current = room.get("agent_status") or {}
                    if current.get("run_id") == latest["run_id"] and current.get("state") != "running":
                        status = current
                    else:
                        phase = latest["phase"]
                        label = "처리를 마쳤습니다." if phase == "done" else "발화 처리에 실패했습니다. 작업 기록을 확인해 주세요."
                        status = dict(run_id=latest["run_id"], state=phase, label=label)
            else:
                status = None
            if status is not None and room.get("agent_status") != status:
                room["agent_status"] = status
                self.db.put("room:" + room_id, room)
                publish_event(self.db, room_id, "agent.status", {"status": status})
            if room.get("agent_pipeline")!=data:
                room["agent_pipeline"]=data
                self.db.put("room:"+room_id,room)
                publish_event(self.db,room_id,"room.updated",{"changed":["agent_pipeline"]})

    def _registered(self, job):
        value = self.db.get(job_key(job))
        return (value is not None and value.get("token")==job.get("token")
                and self.db.get("room:"+job["room_id"]) is not None)

    async def _trace(self, job, stage, state, **metadata):
        current=self.db.get(job_key(job))
        if current is None or current["id"]!=job["id"] or self.db.get("room:"+job["room_id"]) is None:
            return
        if job["phase"] == "executing":
            metadata.update(execution_trace_fields(job))
        else:
            metadata["attempt"] = job["extraction_attempts"] + int(job["revalidation_started"])
        store_trace(self.db,dict(run_id=job["run_id"],step=0,event=stage,call_id=None,created_at=now(),
            payload=dict(job_id=job["id"],extraction_id=job["extraction_id"],stage=stage,state=state,
                         message_ids=job["message_ids"],**metadata)))

    async def _emit(self, job, event):
        if event.get("run_id")!=job["run_id"] or not self._registered(job):
            return
        current=self.db.get(job_key(job))
        if current["phase"]!="executing":
            return
        self.store.checkpoint_call(job,event)
        store_trace(self.db, dict(event, payload=dict(event["payload"], **execution_trace_fields(job))))

    async def _extract(self, job):
        task=self._fresh(job)
        await self._trace(job,"extraction","started")
        started=perf_counter()
        prepared=await asyncio.wait_for(self.port.extract(task,previous=job.get("prepared")),self.extraction_timeout)
        report=prepared.get("extraction_report",{})
        if report.get("status")=="failed":
            transient=bool(set(report.get("issue_codes",[])) & {"auxiliary_request_failed","auxiliary_invalid_output"})
            if transient and self.store.requeue(job,"extraction","auxiliary_transient_failure"):
                await self._trace(job,"extraction","retry_queued",extraction_report=report)
                return
            from backend.services.extraction import record_extraction_failure
            from backend.services.agent_jobs import set_status
            record_extraction_failure(self.db,dict(room_id=job["room_id"],run_id=job["run_id"],extraction_report=report))
            self.store.fail(job,"auxiliary_extraction_failed")
            set_status(self.db,job["room_id"],job["run_id"],"failed",extraction_label(dict(extraction_report=report,completion="needs_input")))
            await self._trace(job,"extraction","failed",extraction_report=report)
            return
        if self.store.finish_extraction(job,prepared):
            await self._trace(job,"extraction","completed",duration_ms=round((perf_counter()-started)*1000,3),
                              extraction_report=prepared.get("extraction_report",{}))

    async def _execute(self, job):
        from backend.services.agent_jobs import decision_snapshot,set_status
        self._restore_observations(job["room_id"])
        with self.db.lock:
            task=self._fresh(job)
            if not job["message_ids"] and task["_defer_execution"]:
                # There are no new facts to apply. Park the exact control until
                # every intervening source has a successful handling receipt.
                intent = dict(control=True, depth=task.get("_continuation_depth", 0))
                outcome = dict(phase="held", reason="deferred_to_newer_input", continuation=intent,
                               public_status=dict(run_id=job["run_id"], state="waiting",
                                                  label="새 발화 처리 후 작업을 계속합니다."))
                self.db.put_many(self.store.completion_records(job, outcome))
                return
            run=self.db.get("run:"+job["run_id"])
            if run and run.get("applied"):
                records=self.store.completion_records(job,{"phase":"done","reason":"already_applied"})
                if records: self.db.put_many(records)
                return
            record=dict(run or {},room_id=job["room_id"],base_versions=deepcopy(task["base_versions"]),
                        message_ids=list(job["message_ids"]),extraction_id=job["extraction_id"],job_id=job["id"])
            self.db.put("run:"+job["run_id"],record)
            snapshot=decision_snapshot(self.db,job["room_id"])
        def is_current():
            return self._registered(job) and decision_snapshot(self.db,job["room_id"])==snapshot
        async def emit(event):
            await self._emit(job,event)
        set_status(self.db,job["room_id"],job["run_id"],"running","검증한 발화로 다음 행동을 판단하고 있습니다.")
        await self._trace(job,"execution","started")
        result=await asyncio.wait_for(self.port.run_prepared(task,job["prepared"],emit,is_current),self.execution_timeout)
        if not self._registered(job):
            return
        if (result.get("run_id"),result.get("room_id"))!=(job["run_id"],job["room_id"]):
            raise ValueError("Agent result identity does not match registered job")
        with self.db.lock:
            current=is_current()
            if not current:
                await self._trace(job,"execution","stale")
                if not self.store.requeue(job,"execution","state_changed"):
                    self.store.fail(job,"stale_attempt_limit")
                return
            decision = result.get("decision_report", {})
            reason = decision.get("reason", "completed")
            deferred = reason == "newer_messages_pending"
            depth = task.get("_continuation_depth", 0)
            state = ("done" if result["completion"] == "done" else
                     "failed" if decision.get("status") == "failed" or result.get("tool_failures") else
                     "needs_input" if result.get("questions") else "waiting")
            status = dict(run_id=job["run_id"], state=state, label=extraction_label(result))
            outcome = dict(phase="done", reason="deferred_to_newer_input" if deferred else reason,
                           last_processed_message_id=result.get("last_processed_message_id"), public_status=status)
            if deferred or (reason == "round_limit" and depth < 2):
                pending = [r["request_id"] for r in result.get("request_states", [])
                           if r.get("status") not in TERMINAL_REQUESTS | {"failed"}]
                outcome["continuation"] = dict(request_ids=pending, pending_items=bool(result.get("pending_item_ids")),
                                               depth=max(1, depth) if deferred else depth + 1,
                                               # Canonical plan calculations can span rounds with no request IDs.
                                               resume_plan=reason == "round_limit" and not result.get("request_states"))
            extra=self.store.completion_records(job,outcome)
            applied=bool(extra) and apply_agent_result(self.db,result,extra_records=extra)
            if not applied:
                self.store.fail(job,"extraction_failed" if result.get("extraction_report",{}).get("status")=="failed" else "apply_rejected")
        step=max((e["step"] for e in self.db.traces.get(job["run_id"],{}).get("events",[])),default=0)+1
        if self.db.get("room:"+job["room_id"]) is not None:
            store_trace(self.db,dict(run_id=job["run_id"],step=step,event="state_applied",call_id=None,created_at=now(),
                payload=dict(applied=applied,versions=self.db.get("room:"+job["room_id"])["versions"],job_id=job["id"],extraction_id=job["extraction_id"],
                             **execution_trace_fields(job))))
            if applied:
                set_status(self.db, job["room_id"], job["run_id"], status["state"], status["label"])
            else:
                set_status(self.db,job["room_id"],job["run_id"],"failed",extraction_label(result))
        await self._resume_deferred(job["room_id"])

    async def _resume_deferred(self, room_id):
        room = self.db.get("room:" + room_id)
        jobs = self.store.jobs(room_id)
        if room is None or any(job["phase"] not in TERMINAL for job in jobs):
            return
        if self._outstanding_sources(room, jobs):
            return
        scheduled = {parent for job in jobs for parent in job["task"].get("_deferred_parent_ids", [])}
        active = {r["request_id"] for r in room.get("agent_requests", [])
                  if r.get("status") not in TERMINAL_REQUESTS | {"failed"}}
        groups = {}
        plan_parents = set()
        for job in jobs:  # Parents precede their children in durable ordinal order.
            outcome = job.get("outcome") or {}
            intent = outcome.get("continuation")
            if not intent and outcome.get("deferred_source_ids"):
                intent = dict(request_ids=outcome.get("deferred_request_ids", []), pending_items=True, depth=1)
            if not intent:
                continue
            # A plan round carries work independently of its (possibly empty)
            # request and item lists. Preserve that intent through parked children.
            if intent.get("resume_plan") or (intent.get("control") and
                    not plan_parents.isdisjoint(job["task"].get("_deferred_parent_ids", []))):
                plan_parents.add(job["run_id"])
            if job["run_id"] in scheduled:
                continue
            if intent.get("control"):
                original = job["task"]
                ids = original.get("_resume_request_ids")
                items = original.get("_resume_item_ids")
                if ids is not None:
                    ids = sorted(active.intersection(ids))
                if items is not None:
                    items = sorted(set(room.get("agent_pending_item_ids", [])).intersection(items))
                if (ids is None and items is None) or ids or items or job["run_id"] in plan_parents:
                    await self.enqueue(room_id, original["goal"], original.get("user_selection"),
                                       resume_ids=ids, resume_items=items, parents=[job["run_id"]],
                                       depth=intent["depth"])
                continue
            ids = active.intersection(intent["request_ids"])
            items = room.get("agent_pending_item_ids", []) if intent["pending_items"] else []
            if ids or items or intent.get("resume_plan"):
                group = groups.setdefault(intent["depth"], dict(ids=set(), items=set(), parents=[]))
                group["ids"].update(ids)
                group["items"].update(items)
                group["parents"].append(job["run_id"])
        for depth, group in groups.items():
            await self.enqueue(room_id, "continue_pending", resume_ids=sorted(group["ids"]),
                               resume_items=sorted(group["items"]), parents=group["parents"], depth=depth)

    async def _worker(self, stage):
        while True:
            self.wake[stage].clear()
            job=self.store.claim(stage)
            if job is None:
                await self.wake[stage].wait()
                continue
            self.active[stage]=job["id"]
            self._progress(job["room_id"])
            try:
                if stage=="extraction": await self._extract(job)
                else: await self._execute(job)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                code=getattr(error,"code",None)
                if code=="prepared_context_stale" and self.store.requeue(job,"extraction",code,revalidation=True):
                    await self._trace(job,"extraction","revalidation_queued")
                else:
                    held=code in {"prepared_source_invalid","prepared_context_stale"}
                    records=self.store.completion_records(job,{"phase":"held","reason":code}) if held else {}
                    if records: self.db.put_many(records)
                    else: self.store.fail(job,code or type(error).__name__)
                    from backend.services.agent_jobs import set_status
                    set_status(self.db,job["room_id"],job["run_id"],"held" if held else "failed","발화 처리에 실패했습니다. 작업 기록을 확인해 주세요.")
            finally:
                self.active.pop(stage,None)
                self._progress(job["room_id"])
                self.notify()
                await self.reconcile()

    async def work(self):
        self.store.recover()
        await self.reconcile(startup=True)
        self.started.set()
        self.notify()
        workers=[asyncio.create_task(self._worker(stage)) for stage in ("extraction","execution")]
        try:
            await asyncio.gather(*workers)
        finally:
            for worker in workers: worker.cancel()
            for worker in workers:
                with suppress(asyncio.CancelledError): await worker
            self.started.set()
            self.notify()
