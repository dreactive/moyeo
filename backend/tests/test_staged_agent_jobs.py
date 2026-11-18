"""Real stage coordination tests use events, isolated stores and source receipts."""
import asyncio
from copy import deepcopy
import pytest
from backend.db import Database
from backend.services.agent_jobs import AgentJobs
from backend.services.messages import save_message


def clean_room(room, room_id="room-fixture"):
    value = deepcopy(room)
    value.update(room_id=room_id, messages=[], seq=0, items=[], constraints=[], questions=[],
                 current_plan=None, review_plan=None, confirmed_plan=None, active_target=None,
                 confirmations=[], conflicts=[], agent_requests=[], agent_pending_item_ids=[])
    value["versions"] = dict.fromkeys(value["versions"], 0)
    return value


def result_for(task):
    return dict(run_id=task["run_id"], room_id=task["room_id"], base_versions=task["base_versions"],
                item_proposals=[], constraint_proposals=[], support_observations=[], questions=[],
                observations=[], conflicts=[], plan_draft=None, completion="done",
                last_processed_message_id=task["recent_messages"][-1]["id"] if task["recent_messages"] else None,
                extraction_report=dict(status="ok", issue_codes=[], rejected_message_ids=[], attempts=1))


class StagedPort:
    def __init__(self):
        self.extracted, self.executed = [], []
    async def extract(self, task, previous=None):
        ids = [m["id"] for m in task["recent_messages"]]
        self.extracted.append((task["room_id"], ids))
        return dict(message_ids=ids, room_id=task["room_id"])
    async def run_prepared(self, task, prepared, emit, is_current=None):
        assert prepared["message_ids"] == [m["id"] for m in task["recent_messages"]]
        self.executed.append((task["room_id"], prepared["message_ids"]))
        return result_for(task)


async def stop(worker):
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


def test_extraction_overlaps_tool_wait_without_advancing_execution_cursor(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture", clean_room(room))
        executing=asyncio.Event(); release=asyncio.Event(); second_extracted=asyncio.Event()
        class Port(StagedPort):
            async def extract(self, task, previous=None):
                value=await super().extract(task, previous)
                if len(self.extracted)==2: second_extracted.set()
                return value
            async def run_prepared(self, task, prepared, emit, is_current=None):
                if not self.executed:
                    self.executed.append((task["room_id"],prepared["message_ids"]))
                    executing.set(); await release.wait()
                    return result_for(task)
                return await super().run_prepared(task,prepared,emit,is_current)
        port=Port(); jobs=AgentJobs(db,port); worker=asyncio.create_task(jobs.work())
        try:
            a=save_message(db,"room-fixture","u1","오동도 찾아줘."); await jobs.enqueue("room-fixture","new_message")
            await asyncio.wait_for(executing.wait(),1)
            b=save_message(db,"room-fixture","u2","자산공원도 찾아줘."); await jobs.enqueue("room-fixture","new_message")
            await asyncio.wait_for(second_extracted.wait(),1)
            assert db.get("extracted-message:room-fixture")==b["id"]
            assert db.get("processed-message:room-fixture") is None
            assert port.extracted==[("room-fixture",[a["id"]]),("room-fixture",[b["id"]])]
            release.set(); await asyncio.wait_for(jobs.queue.join(),3)
            assert db.get("processed-message:room-fixture")==b["id"]
            assert len(port.extracted)==2
        finally: release.set(); await stop(worker)
    asyncio.run(scenario())


def test_newer_backlog_defers_old_tools_but_applies_source_batches_in_order(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture",clean_room(room)); flags=[]
        class Port(StagedPort):
            async def run_prepared(self,task,prepared,emit,is_current=None):
                flags.append((prepared["message_ids"],task.get("_defer_execution",False)))
                return await super().run_prepared(task,prepared,emit,is_current)
        port=Port(); jobs=AgentJobs(db,port)
        a=save_message(db,"room-fixture","u1","오동도 찾아줘."); await jobs.enqueue("room-fixture","new_message")
        b=save_message(db,"room-fixture","u1","그 조회는 취소하자."); await jobs.enqueue("room-fixture","new_message")
        worker=asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(),3)
            assert flags[:2]==[([a["id"]],True),([b["id"]],False)]
            assert db.get("processed-message:room-fixture")==b["id"]
        finally: await stop(worker)
    asyncio.run(scenario())


def test_startup_recovers_saved_messages_without_enqueue_receipt(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture",clean_room(room))
        message=save_message(db,"room-fixture","u1","새 메시지 저장 직후 프로세스가 종료됨")
        port=StagedPort(); jobs=AgentJobs(db,port); worker=asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(),3)
            assert port.extracted==[("room-fixture",[message["id"]])]
            assert db.get("processed-message:room-fixture")==message["id"]
        finally: await stop(worker)
    asyncio.run(scenario())


def test_wrong_prepared_result_identity_does_not_loop_or_apply(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture",clean_room(room))
        class Port(StagedPort):
            async def run_prepared(self,task,prepared,emit,is_current=None):
                value=await super().run_prepared(task,prepared,emit,is_current); value["run_id"]="wrong"; return value
        port=Port(); jobs=AgentJobs(db,port)
        save_message(db,"room-fixture","u1","오동도 찾아줘."); receipt=await jobs.enqueue("room-fixture","new_message")
        worker=asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(),3)
            assert len(port.executed)==1
            assert not db.get("run:"+receipt["run_id"]).get("applied")
            assert db.get("processed-message:room-fixture") is None
        finally: await stop(worker)
    asyncio.run(scenario())


def test_overlapping_extraction_and_execution_keep_both_run_traces(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture",clean_room(room)); entered=asyncio.Event(); release=asyncio.Event(); extracted=asyncio.Event()
        class Port(StagedPort):
            async def extract(self,task,previous=None):
                value=await super().extract(task,previous)
                if len(self.extracted)==2: extracted.set()
                return value
            async def run_prepared(self,task,prepared,emit,is_current=None):
                if not self.executed:
                    self.executed.append((task["room_id"],prepared["message_ids"]))
                    entered.set(); await release.wait()
                await emit(dict(run_id=task["run_id"],step=1,event="decision",call_id=None,created_at="2026-11-19T00:00:00Z",payload={"summary":"execution"}))
                return result_for(task)
        port=Port(); jobs=AgentJobs(db,port); worker=asyncio.create_task(jobs.work())
        try:
            save_message(db,"room-fixture","u1","A"); a=await jobs.enqueue("room-fixture","new_message"); await asyncio.wait_for(entered.wait(),1)
            save_message(db,"room-fixture","u2","B"); b=await jobs.enqueue("room-fixture","new_message"); await asyncio.wait_for(extracted.wait(),1)
            assert a["run_id"] in db.traces and b["run_id"] in db.traces
            assert any(e["event"]=="extraction" for e in db.traces[b["run_id"]]["events"])
            release.set(); await asyncio.wait_for(jobs.queue.join(),3)
            assert any(e["event"]=="decision" for e in db.traces[a["run_id"]]["events"])
        finally: release.set(); await stop(worker)
    asyncio.run(scenario())


def test_room_delete_during_extraction_never_resurrects_jobs_or_room(room):
    from backend.services.rooms import delete_room
    async def scenario():
        db=Database(":memory:"); value=clean_room(room); db.put("room:room-fixture",value)
        entered=asyncio.Event(); release=asyncio.Event()
        class Port(StagedPort):
            async def extract(self,task,previous=None):
                entered.set(); await release.wait(); return await super().extract(task,previous)
        port=Port(); jobs=AgentJobs(db,port); worker=asyncio.create_task(jobs.work())
        try:
            save_message(db,"room-fixture","u1","A"); await jobs.enqueue("room-fixture","new_message"); await asyncio.wait_for(entered.wait(),1)
            delete_room(db,"room-fixture",value["members"][0]["user_id"]); release.set(); await asyncio.wait_for(jobs.queue.join(),3)
            assert db.get("room:room-fixture") is None
            assert not db.scan("pipeline-job:room-fixture:")
            assert not port.executed and not db.traces
        finally: release.set(); await stop(worker)
    asyncio.run(scenario())


def test_transient_extraction_failure_retries_only_extraction(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture",clean_room(room))
        class Port(StagedPort):
            async def extract(self,task,previous=None):
                value=await super().extract(task,previous)
                if len(self.extracted)==1:
                    value["extraction_report"]={"status":"failed","issue_codes":["auxiliary_request_failed"],"attempts":1}
                return value
        port=Port(); jobs=AgentJobs(db,port); message=save_message(db,"room-fixture","u1","오동도 찾아줘.")
        await jobs.enqueue("room-fixture","new_message"); worker=asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(),3)
            assert len(port.extracted)==2 and len(port.executed)==1
            assert db.get("processed-message:room-fixture")==message["id"]
        finally: await stop(worker)
    asyncio.run(scenario())


def test_extraction_failure_stays_failed_while_later_message_makes_progress(room):
    async def scenario():
        db=Database(":memory:"); db.put("room:room-fixture",clean_room(room))
        class Port(StagedPort):
            async def extract(self,task,previous=None):
                value=await super().extract(task,previous)
                if task["recent_messages"][0]["text"]=="bad":
                    value["extraction_report"]={"status":"failed","issue_codes":["auxiliary_request_failed"],"attempts":1}
                return value
        port=Port(); jobs=AgentJobs(db,port)
        bad=save_message(db,"room-fixture","u1","bad"); await jobs.enqueue("room-fixture","new_message")
        good=save_message(db,"room-fixture","u2","good"); await jobs.enqueue("room-fixture","new_message")
        worker=asyncio.create_task(jobs.work())
        try:
            await asyncio.wait_for(jobs.queue.join(),3)
            assert len(port.extracted)==3 and len(port.executed)==1
            assert db.get("failed-extraction:room-fixture")[bad["id"]]["status"]=="retry_required"
            assert db.get("processed-message:room-fixture")==good["id"]
            assert all(j["phase"] in ("failed","done") for j in jobs.pipeline.store.jobs())
        finally: await stop(worker)
    asyncio.run(scenario())
