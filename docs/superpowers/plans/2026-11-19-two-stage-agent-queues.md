# Two-stage Agent Queues Implementation Plan

> **For agentic workers:** Use subagent-driven development with test-first regressions. No individual commits: user requires one final implementation commit and push to origin/develop after verification.

**Goal:** Overlap one auxiliary extraction worker with one existing Qwen/tool execution worker while preserving source order, freshness, recovery and current service contracts.

**Architecture:** SQLite-backed per-room stage jobs carry raw structured interpretation and provenance. Execution always grounds against fresh room state and creates new actual candidates. Two independent workers share bounded durable queues; context refresh returns to the extraction stage. Legacy run-only fixture ports retain serial compatibility.

**Tech Stack:** Python/FastAPI/asyncio/Pydantic/LangChain, existing records SQLite table, supplied Qwen+LoRA and original judge, existing frontend.

**Spec:** docs/superpowers/specs/2026-11-19-two-stage-agent-queues-design.md

## Global Constraints

- Base origin/develop b0cb8f0; preserve its frontend/auth/room lifecycle integration.
- Preserve supplied weights, LoRA, judge, original production DB and running server. Do not include original worktree's five shared-env edits.
- Exactly one final commit, normal non-force push HEAD:develop; preserve any intervening remote changes.
- Auxiliary worker1 and execution worker1; Qwen lock1. No tools/Qwen in extraction. No auxiliary API call in execution stage.
- Two logical durable queues, per-room FIFO, fair rooms, <=20 source messages,0ms batching delay,64 global/8 per-room prepared window.
- Current raw-score argmax, exact selected args, grounding, final human approval and canonical calculations remain authoritative.
- Existing C-revised2 semantic issues stay deferred. This is concurrency/lifecycle work.

## Review Focus

- A tool wait must not block extraction of later messages; later extracted messages cannot advance execution cursor.
- A late correction/cancellation cannot execute stale calls or publish stale plan/response; independently valid read observations may survive.
- Restart at extraction, dispatch, return and apply boundaries must not duplicate state or erase accepted messages.
- Cross-room/run/author/range tampering, deleted rooms and trace callbacks cannot resurrect or cross-apply data.
- Persistent queue backlogs must drain fairly under bounded readiness and attempts; failures cannot form retry loops.

## Shared Interfaces

- AI: async extract_auxiliary(task,auxiliary,*,previous=None) -> serializable prepared envelope; ground_auxiliary(task,envelope) -> existing grounded result or typed stale/invalid provenance exception. Existing prepare_auxiliary remains wrapper.
- Runtime/LocalAIBridge: async extract(task,previous=None); async run_prepared(task,prepared,emit_trace,is_current=None). Prepared execution never calls the auxiliary directly. source_mode distinguishes current and saved-context retry.
- Backend store: PipelineStore(db,*,max_attempts=2,ready_limit=64,per_room_ready_limit=8). Jobs include id/run_id/extraction_id/room_id/ordinal/task/message_ids/boundary_seq/phase/attempt counters/token/prepared/timestamps/tool_receipts/outcome.
- Store methods: create(task), jobs(room_id=None), covered_ids(room_id), claim(stage), finish_extraction(job,prepared), requeue(job,stage,reason,*,revalidation=False), fail(job,reason), completion_records(job,outcome), checkpoint_call(job,event), restore_observations(room_id), recover(), purge_room(room_id), counts(room_id=None). Claim returns None or a copy with token; mutating methods CAS room existence + token + active phase and return bool/records. Atomic completion records are consumed by apply_agent_result(extra_records=...).
- Root coordinator may refine store API with explicit messages to both implementers; preserve signatures once implementation begins.
- task._defer_execution tells AI runner to ground/prepare facts and pending requests without invoking Qwen/tools when later unprocessed source exists. task._pipeline_context/saved source IDs must never authorize arbitrary historical state effects.

### Task 1: AI extraction envelope and fresh grounding

Ownership: ai/auxiliary.py, new ai/prepared_auxiliary.py if useful, ai/runtime.py, ai/judged_runner.py, backend/adapters/local_ai.py, backend/ports.py, corresponding AI tests.

- [x] Write failing tests for extraction/ground separation, explicit stale-state reuse, dependent refresh routing, tampered provenance and saved-context retry.
- [x] Split before ground_batch. Persist source provenance and dependency basis; latest grounding stays authoritative.
- [x] Implement bounded extraction-stage refresh and safe first-pass retention; execution raises a typed refresh request instead of calling auxiliary.
- [x] Add fresh exact item rebinding or bounded refresh to prevent duplicate proposals from queued snapshots; preserve item versions and author identity.
- [x] Add prepared runner and defer-execution path retaining facts/request obligations without tools/plan or cursor overreach.
- [x] Run focused and full AI suite; no per-task commit.

### Task 2: Durable queues and recovery store

Ownership: new backend/services/pipeline_store.py and backend/tests/test_pipeline_store.py only.

- [x] Add failing persistence/FIFO/fairness/claim-token/backpressure/recovery/deletion/idempotence tests.
- [x] Implement the shared store using existing Database.scan/put_many/RLock; no external broker.
- [x] Store checkpoints and terminal completion/cursor records for atomic apply; recover interrupted stages with bounded attempts and run.applied fence.
- [x] Run focused store tests; no per-task commit.

### Task 3: Two-worker backend integration

Ownership: root: backend/services/agent_jobs.py, new agent_pipeline.py, app lifecycle if necessary, agent_apply.py, rooms.py, traces.py, integration tests and optional frontend phase rendering.

- [x] Write red overlap/serial-order/stale-cancel/trace/close-room/crash-gap/drain regressions with asyncio.Event and isolated databases.
- [x] Reserve nonoverlapping bounded source windows on enqueue, reconcile persisted unqueued messages on startup and recover jobs before workers.
- [x] Run extraction and execution independently; fresh execution snapshot and after-trace dispatch checks remain.
- [x] Newer backlog defers old external work, applies facts in sequence and resumes pending requests after catch-up with bounded continuations.
- [x] Commit room state plus terminal job/cursor records atomically, retain reusable read checkpoints and discard stale plans/responses.
- [x] Trace extraction and execution with registered IDs, queue timings and per-stage identity guards. Public states remain compatible; phase status is additive.
- [x] Room deletion clears persistent stage records/checkpoints and late callbacks are ignored. Legacy fixture clients and newest remote features stay working.

### Task 4: Verification, review and one remote commit

- [x] Run complete AI/Backend(integration included)/frontend suites and diff checks.
- [x] Controlled serial/legacy-burst/two-stage-burst comparison: meaning, ordering, duplicates, stale work, overlap and time components; do not claim real speedups from synthetic delays.
- [x] Actual auxiliary + supplied Qwen + live provider path in an isolated DB verifies prepared facts, Qwen same-args dispatch, output apply and overlapping extraction. Original service untouched.
- [x] Independent whole-change review; resolve important findings and rerun affected tests.
- [x] Record evidence/limits/contracts and preservation; final test totals: AI473, Backend301 including integration, Frontend266. Actual live14/14 and independent re-review approved.
- Publication procedure: one final commit, then normal non-force push to origin/develop and compare remote SHA. The final response records the resulting commit and verified remote state.
