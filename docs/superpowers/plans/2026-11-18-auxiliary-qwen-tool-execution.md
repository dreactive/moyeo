# Auxiliary Context and Qwen Tool Selection Implementation Plan

> **For agentic workers:** Use parallel isolated component implementation with test-first verification and one whole-branch review. The user explicitly authorized full execution and a final commit, without 300-character changes or further plan approval.

**Goal:** Restore supplied Qwen+LoRA judge as the service decision maker, with external auxiliary extraction/context completion, real-candidate exceptions, and existing tool execution.
**Architecture:** Auxiliary structured facts are grounded to existing proposal contracts; candidate builders inspect independent per-tool readiness; the unchanged supplied judge scores actual choices; the runner executes only the selected validated action. Existing backend room application and frontend traces remain the integration boundaries.
**Tech Stack:** Python, LangChain structured output, Transformers/PEFT Qwen, existing FastAPI/SQLite and frontend ES modules.
**Spec:** docs/superpowers/specs/2026-11-18-minimal-tool-inputs-design.md

## Global constraints

- Preserve supplied submission code, base weights, LoRA and tokenizer; judge inference uses the supplied scoring helper.
- Preserve original DB and running server. All verification writes use isolated worktree databases. Keep original .env secrets out of logs and Git.
- Branch codex/qwen-judge-tool-execution starts at develop cc6a461 in a separate managed worktree.
- No automatic tool fallback, invented arguments, arbitrary score thresholds, synthetic padding to four, or remote auxiliary tool execution.
- Commit completed reviewed work as a meaningful feature commit; no 300-character splitting, push or merge.

## Review focus

- Compound rejection/alternative and short replies bind to the proper current author and target.
- Missing user information differs from history lookup and required tool observations.
- Candidate underflow, zero candidates, and scoring errors never execute candidate zero by default.
- Scored calls and execution arguments remain identical; stale room state cannot apply obsolete effects.
- Real judge selection and real provider calls must be distinguished from fixtures and auxiliary API calls.

## Tasks

### 1. Auxiliary structured extraction and context completion
Files: ai/auxiliary*.py and related tests. Interface: async prepare_auxiliary(task, auxiliary) -> dict with existing item_proposals/constraint_proposals/support_observations/questions/extraction_report plus analysis. External client extract(task, stage=1) -> schema-validated dict; fixture client is explicit.
- [x] Write and run failing compound-intent, source/owner, history-only reference, unsupported/noop and missing-credential tests.
- [x] Implement LangChain external structured API adapter and bounded relevant-context completion without Qwen generation.
- [x] Run component tests; keep existing condition provenance validation.

### 2. Grounded candidate preparation
Files: ai/decision_candidates.py and related tests. Interfaces: build_decision_candidates(task, analysis=None) -> {branch,candidates}; compact_decision_context(task, analysis,candidates) -> dict.
- [x] Test independent per-tool readiness, real argument equality, valid max3 tool alternatives, invalid questions/direct/unsupported, and zero/one/two actual candidates.
- [x] Implement code-owned candidate creation without global phase gating or arbitrary additional questions.
- [x] Run tests; preserve omitted work and stable source mappings.

### 3. Supplied judge wiring
Files: ai/models/local_qwen.py, worker.py, fake.py, new scoring helper/tests.
Interface: score_candidates(context:dict,candidates:list[dict]) -> list[float] on backend and ModelWorker.
- [x] Test supplied judge helper invocation with active LoRA, variable real candidate counts, finite scores, oversized input rejection, and serialized model access.
- [x] Restore scorer using original submission.judge without changing supplied artifacts or reloading model.
- [x] Provide explicit fixture scoring, not a hidden live fallback; run tests.

### 4. Workflow, backend and visible traces
Files: ai/runner.py/runtime.py/contracts.py, backend config/application/status integration, frontend existing trace view and tests.
- [x] Test auxiliary then one final judge comparison, exact selected tool execution, non-tool responses, failure receipt/cursor behavior and no-op preservation.
- [x] Integrate analysis/proposal preview into frozen decision task, real selected-action execution and accurate completion/status.
- [x] Preserve DB/room application invariants and existing tool semantics; update meaningful obsolete candidate-only tests.
- [x] Run full AI/backend/frontend suites and targeted integration checks.

### 5. Real model validation and delivery
Files: isolated live audit script/artifacts under .planning, committed verification report/docs.
- [x] Snapshot and hash original DB/adapter assets without writing them.
- [x] Validate provided LoRA judge chooses between real candidates and selected calls reach real tool execution on isolated data; include search, actual missing info, compound opinion and scoring failures.
- [x] Measure actual candidate counts, compact input sizes and stage latencies. Use real auxiliary API only when configured; never label fixtures as live.
- [x] Independent branch review, fix important findings with regressions, run affected checks, update report and commit the feature.

## Completion evidence

- Actual supplied Qwen/LoRA: four response types verified; two real tool candidates scored, selected call reached Kakao HTTP search. Scripted auxiliary inputs explicitly labelled.
- Original model/tokenizer/adapter files and existing DB hashes unchanged. Original server was not restarted.
- External auxiliary API remains unverified because the user intentionally left OPENAI_API_KEY empty; actual LangChain JSON-schema transport and failures are verified with MockTransport.
- Independent review fixes include open questions, pending-place continuation, current-request ordering, source/polarity and support-answer contracts, recalculation basis, and unsupported capability grounding.
- Final tests and measured timings are recorded in docs/verification/2026-11-18-qwen-judge-tool-execution.md.
