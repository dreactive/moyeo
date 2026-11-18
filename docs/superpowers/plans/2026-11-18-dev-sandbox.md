# Developer Swagger Sandbox Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Follow the repository's small-commit workflow.

**Goal:** Execute five tools and deliver an utterance directly to the Agent through developer-only Swagger operations.

**Architecture:** Typed FastAPI operations reuse the registry and AI runtime, with caller-supplied isolated context and existing login/developer token checks. Backend-owned examples support reproducible fixture calls.

**Tech Stack:** Python, FastAPI, Pydantic, existing pytest/TestClient and AI runtime.

**Spec:** `docs/superpowers/specs/2026-11-18-dev-sandbox-design.md`

## Global Constraints

- Work on `develop`; preserve unrelated untracked files and local-only instructions.
- No new dependencies; Backend boots without AI until a sandbox execution needs it.
- Test calls never apply results to real rooms or enqueue jobs.
- Keep configured fake/live provenance and existing Agent behavior.
- Implement, verify and commit small working units before proceeding.

## Review Focus

- Missing login/token cannot execute tools or initialize a model.
- Swagger examples for all five tools execute with fixture mode.
- Calculation inputs cannot bypass canonical facts; omitted arguments are derived.
- Invalid context, provider failures and missing dependencies produce safe HTTP errors.
- Utterance author, fresh run/message IDs, traces and shutdown preserve isolation.

## Task 1: Shared developer authentication and schemas

Files: `backend/dev_auth.py`, `backend/routes/dev.py`, `backend/dev_schemas.py`, `backend/dev_sandbox_fixture.json`, `backend/dev_examples.py`, `backend/tests/test_dev_sandbox.py`.

- [x] Write failing tests for Swagger developer security and invalid-token denial.
- [x] Add shared APIKeyHeader authentication and adopt it in the existing trace route.
- [x] Define typed context, tool arguments, requests and documented fixture examples.
- [x] Verify existing developer trace tests; commit each working unit.

## Task 2: Direct tool operations

Files: `backend/app.py`, `backend/services/dev_sandbox.py`, `backend/routes/dev_sandbox.py`, `backend/tests/test_dev_sandbox.py`.

Interfaces: `execute_tool(body, name, settings)` returns tool/result/observation/context; `sandbox_errors()` maps execution failures; `DevContext` supplies existing task fields.

- [x] Write failing HTTP tests, then expose search, details and route operations one at a time.
- [x] Return reusable observations/context and configured provider provenance.
- [x] Write failing tests, then expose itinerary and cost calculations with canonical argument derivation and explicit-input validation.
- [x] Test authentication for every operation, invalid context and provider failures.
- [x] Run focused tests after each small unit; commit verified units.

## Task 3: Agent utterance operation

Files: `backend/app.py`, `backend/services/dev_sandbox.py`, `backend/routes/dev_sandbox.py`, `backend/tests/test_dev_sandbox.py`.

Interfaces: lazy `app.state.dev_agent` reuses `LocalAIBridge`; utterance response includes model/provider mode, result and sanitized trace.

- [x] Write failing tests for lazy runtime creation/reuse/closure and implement lifespan ownership.
- [x] Write failing tests for author validation, fresh synthetic message/run and read-only database behavior.
- [x] Implement the utterance operation with supported goals and safe error mapping.
- [x] Verify real fake/fixture Agent invocation and returned trace.
- [x] Commit verified small units.

## Task 4: Documentation and delivery

- [x] Document Swagger login/Authorize, all operations, context chaining and fake/live behavior in `backend/README.md`.
- [x] Run full Backend and AI suites and independent code review; fix material findings.
- [x] Check staged files exclude personal instructions and unrelated documents.
- [ ] Push `develop` without force and create/update the `master <- develop` PR.
- [ ] Report tests, commit range, push and PR; distinguish offline coverage from unrun live calls.

