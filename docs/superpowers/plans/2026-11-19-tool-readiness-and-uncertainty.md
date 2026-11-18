# 도구 준비조건과 불확실성 개선 구현 계획

> **For agentic workers:** Use the approved spec and task ownership below. Follow test-first regression development; do not commit individual tasks. The user requires one implementation commit after all tasks and verification.

**Goal:** 도구별 최소 입력·부분 결과·요청별 진행을 실제 Qwen 최종 선택과 기존 동의 화면에 연결한다.

**Architecture:** 기존 외부 보조 Structured Output과 요청 기록을 확장한다. 코드는 근거 있는 호출을 구성하고 제공 Qwen judge가 선택하며, 기존 실행기·Backend가 결과를 검증하고 저장한다. 사람의 동의·정보 확인·요청 처리는 별도로 표시한다.

**Tech Stack:** Python/FastAPI/Pydantic/LangChain, 제공 Qwen2.5-1.5B+LoRA, 기존 SQLite 저장, vanilla JS/Node tests.

**Spec:** `docs/superpowers/specs/2026-11-19-tool-readiness-and-uncertainty-design.md`

## Global Constraints

- 제공 Qwen·LoRA·토크나이저·`submission/judge.py`와 원시 채점/argmax를 보존한다.
- 기존 DB·대화방·확정 기록을 변경·초기화하지 않는다. 실제 통합 검증은 격리된 저장/테스트방을 사용한다.
- 보조 모델은 도구명/실행 순위/정답을 지정하지 않는다. 모든 실제 도구 실행은 Qwen 선택 후 같은 인자로 수행한다.
- 타입·원문·작성자·소유권·참조·canonical 계산 인자·최신 상태 검사와 최종 확정 조건을 유지한다.
- 후보는 실제 수만 사용하고 채점 실패 시 임의 대체하지 않는다.
- 이번 구현 완료 후 관련 파일만 하나의 커밋으로 기록한다. 다른 작업의 변경은 유지하고 포함하지 않는다.

## Working tree / coordination

이미 격리된 `codex/qwen-judge-tool-execution` worktree에서 수행한다. 시작 HEAD는 `18ec906`이다. 선행 미커밋 파일 `ai/auxiliary_client.py`, `ai/settings.py`, `backend/config.py`, `ai/tests/test_shared_env.py`, `shared_env.py`는 소유하지 않는다. 별도 index 기반 검증으로 이 변경 없는 커밋 상태도 확인한다.

독립 파일 영역은 병렬로 구현하고, 통합 담당이 공통 계약·runner·Backend·Qwen 입력을 연결한다. 에이전트는 자신의 영역만 수정하고 커밋하지 않는다. 판단과 검증 기록은 `.planning/tool-readiness-implementation/progress.md`에 보존한다.

## Shared interfaces

- `analysis.requests`: 기존 필드 + 조회 목적(기존 `place_details` 호환, `place_lookup`), 필요한 정보(`requested_fields`: location/details/price/opening_hours), 정정/취소(`operation`: request/cancel). 다른 사용자 행위는 근거 있는 `service_request`로 보존해 미지원 부분을 별도 완료할 수 있게 한다.
- Grounded request retains `request_id`, `owner_id`, `source_message_id`, `evidence`, names/refs, `context_evidence`, and unresolved target names. Current request and source scope are validated before candidate construction.
- `request_states`: 기존 완료/대기 참조 + `response`(실제 응답 문자열), `result_refs`, `error_code`; `cancelled`, `unsupported`, `failed`는 명시적인 종료/보류 이유. 완성되지 않은 lookup은 `pending`/`needs_context`/`needs_input`을 구분한다.
- `AgentResult.partial_results`: optional map with keys `build_itinerary`, `calculate_costs` and actual chosen tool results. Backend stores it as `room.agent_results={run_id,versions,...partial_results}` after applying versions. It is an output channel, never a second calculator/executor.
- `build_itinerary` result adds `unplaced_items: [{item_id,place_ref,reason}]` and `missing_observations`; unknown hours are data gaps, not forged `constraint_value` questions.
- `plan_draft`/snapshot may carry optional `unplaced_items`/`missing_observations`; selected IDs retain active unplaced items. `validation` remains non-ready until the full existing final checks pass.
- Frontend reads `agent_requests` and optional `agent_results`; frozen review data remains the displayed plan. Partial outputs are clearly labeled by their own run/basis, never shown as confirmed or attached as historical votes.

## Review Focus

- Mixed new/known lookup targets do not force details for location-only requests or discard valid targets.
- Unselected/stale/failed results cannot publish completion, questions, financial facts or confirmation.
- Unknown tolls and missing visits must not disappear when calculation gates are relaxed.
- New chat/cancellation must not erase terminal request history or make cancelled work resume.
- Support/confirmation-only changes update all relevant panels without recoloring an old snapshot with current votes.

### Task 1: Auxiliary interpretation and candidate preparation

**Ownership:** `ai/auxiliary_schema.py`, `ai/auxiliary.py`, `ai/auxiliary_grounding.py`, `ai/auxiliary_requests.py`, `ai/condition_grounding.py`, `ai/decision_candidates.py`, `ai/prompts/auxiliary.txt`, corresponding new/existing auxiliary/candidate tests.

- [x] Add failing regressions for clause-scoped budget negation, clipped support quote, second-pass missing preservation, mixed known/new lookup, history before search, cancellation and unsupported negation.
- [x] Extend existing structured schema/grounding with shared request interfaces; preserve old request intents and deterministic evidence-checked request IDs.
- [x] Prepare target-specific search/details/direct/question/unsupported candidates with real args; do not suppress actionable ambiguity questions solely because requests exist.
- [x] Validate full request relevance and preserve missing targets, source ownership, latest corrections and deferred work.
- [x] Run focused auxiliary/candidate regressions and report observed failures-to-passes and compatibility implications.

### Task 2: Providers and partial calculations

**Ownership:** `ai/providers/`, `ai/planning.py`, `ai/cost_inputs.py`, `ai/tools/`, `ai/outcome.py`, `ai/questions.py`, related provider/planning/calculation tests. Do not change `ai/tools/definitions.py` (integration owns schemas).

- [x] Reproduce matching, missing-hours, overnight/no-closure, inactive-place, partial-cost and partial-itinerary failures with local data.
- [x] Normalize place identity while retaining branch ambiguity; validate cache date/coordinate/time suitability and label actual execution source.
- [x] Split tool readiness from final readiness, preserve active selected items, unknown toll lines and canonical argument equality.
- [x] Return calculable visits plus unplaced/missing observations; preserve actual known costs and null complete totals.
- [x] Expose only actually observed chosen calculations through `result.partial_results`; assemble drafts with both outputs without relaxing ready/confirmation checks.
- [x] Run provider/calculation/legacy outcome tests and report exact interface additions.

### Task 3: UI agreement, uncertainty and progress

**Ownership:** `frontend/` (except generated assets). Existing endpoint schemas continue; use optional shared fields.

- [x] Add failing DOM/adapter regressions for agreement badges/counts/opposition, unknown costs/hours, per-request partial completion and cancellation, support-only redraws, historical version correctness.
- [x] Carry existing Backend item state into map pins, visits and detail with text/legend; green only when matching displayed confirmed version.
- [x] Show plan-level cost acceptance separately from data unknowns and show actual partial results in existing work/cost/route panels without replacing frozen review semantics.
- [x] Show pending/completed/unsupported/failed/cancelled requests, real response/results and unplaced items; no fictitious route geometry.
- [x] Run all frontend tests; report any required Backend fields.

### Task 4: Integration, Qwen input and persistence

**Ownership:** controller: `ai/judged_runner.py`, `ai/runner.py`, `ai/models/qwen_judge.py`, `ai/tools/definitions.py`, Backend files, contracts/tests, implementation ledger.

- [x] Add failing end-to-end in-memory tests for cancellation, mixed supported+unsupported, one tool failure with independent work, terminal record/question retention, trace-await correction, stale response rejection and partial result visibility.
- [x] Persist valid request states/results without dropping history; validate new question contracts; carry optional partial fields through versioned plans and room state.
- [x] Keep request lifecycle and response completion local to selected work; recheck full snapshot after trace and before dispatch/after HTTP; preserve same-argument execution and bounded rounds.
- [x] Supply detailed faithful tool schemas and compare unchanged judge on compact readable request facts vs old JSON, without recommended choices or weight changes.
- [x] Preserve existing shared-env edits outside this commit and document compatibility changes.

### Task 5: Complete verification and one commit

- [x] Run AI, Backend and frontend suites, then clean staged-tree suites to exclude unrelated modifications.
- [x] Run actual supplied Qwen/LoRA comparisons with competing candidates; record native four-type vs multi-tool behavior and residual errors without interpreting raw scores as probabilities.
- [x] Exercise actual auxiliary→Qwen→selected tools→isolated Backend storage→user-visible results, recording fixture/cached/live paths separately; do not modify production DB/server.
- [x] Fresh whole-change review; resolve material findings and rerun affected checks.
- [x] Record verification and remaining limits. Stage only implementation-owned files and make exactly one final implementation commit.
