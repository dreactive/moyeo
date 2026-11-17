# S2 Backend verification and handoff

Date: 2026-11-18 (Asia/Seoul). Contract v0.2. Owner: S2.
Workspace: C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/.worktrees/trip-s2-be
Branch: work/be. Common base: 20db9c11b2f8a6bdbfa1824720ca9aa502fe71a3.

## Execution evidence

| Stage / C references | Mode | Command / observation | Result |
|---|---|---|---|
| B1 / C41 | fixture; no AI/model | pytest test_isolation.py test_contracts.py. Fresh subprocess blocks ai/torch/transformers/frontend imports, creates app from an empty working directory and performs HTTP requests. Injected port closes once. Frozen TripConfig matches. | PASS |
| B2 / C06-C08/C38/C41 | Backend fixture | Four independent cookie clients join; nonmember 403; immediate POST under blocked Agent; room event ids and cursor replay; SQLite restart persistence; single consumer; latest-input refresh and stale-result requeue. | PASS |
| B3 / C10/C14-C18/C21-C24/C45 | structured fixture inputs, no NLP claim | Unique current-version support; original message author; owner condition edits and confirmation; question shapes/targets and ambiguous-support provenance; 3/4 vs 4/4 identical target; frozen review/new draft; confirmed history. | PASS for Backend state semantics |
| B4 / C22-C23/C26/C32-C33/C37-C38/C47 | fixture observations | Registered run/base checks, copy-before-commit, reference mapping, atomic room/run write, per-room details/context, substantive evidence changes including no draft, timestamp-insensitive hashes, token-gated/redacted trace. | PASS |
| B5 bridge | stub runtime, not real AI | pytest test_local_ai_bridge.py; lazy factory, single lifespan runtime, JSON delegation, close once; failed live runtime propagates. | PASS |
| G3 transport | real HTTP with FixtureAgentPort | backend/.artifacts/g3_server.py and g3_http.py: 4 cookies, 3/4 pending then 4/4 confirmed, POST delivered over SSE to other three clients; dev token gate; only public JS key in HTML. | PASS, fixture seed only |

Latest complete independent suite before final review: backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q => 95 passed, one Starlette deprecation warning about httpx. backend/.artifacts/independent-tests.txt retains local output. Additional focused regressions are recorded in commits and will be included in final verification.

Installation used an isolated backend/.venv, FastAPI, SQLite, httpx, pytest, uvicorn, python-dotenv. No torch/Transformers/PEFT/provider packages were installed for B1-B4. Requirements use explicit separate AI integration dependencies.

## Decisions and deviations

- Native create_worktree twice reported it could not find the actual Git repository. A direct fallback failed with protected .git ref permission. The parent coordinator created this S2 worktree; no product code was written in the shared source.
- Bash task helper was unavailable/hung under the sandbox. PowerShell and .planning/backend-progress.md track B1-B5 directly. The approved implementation plan already existed; no design or approval gate was repeated.
- Small coherent JSON/SQLite/HTTP boundaries occasionally exceed the approximate 300-character target so the unit remains runnable. Work was written, verified, and committed incrementally, never written as one complete implementation then mechanically split.
- One SSE commit (65c17b0) accidentally followed a failed test because PowerShell did not stop on native command failure. 584e712 corrected the stored event shape; subsequent commit commands explicitly stop when pytest exits nonzero. This is not counted as an initial passing verification.
- Ambiguous support uses an opaque question ID carrying AI-classified stance and source message ID (question:support_target:{stance}:{message_id}); Backend verifies original author and current item. It never re-extracts natural language or creates another person's/official vote. S3 coordination is pending confirmation of the same ID rule.
- A new personal condition proposal changes the structured input version; original confirmed conditions remain until owner confirmation supersedes them. A same-value hard/preference change is a new pending proposal.
- Observations and sanitized trace are separate room-scoped process memory, while room snapshots/events/confirmation history are SQLite. This respects the provider retention boundary and keeps product data alive when trace is disabled.

## Actual limits

Backend fixture tests do not verify extraction, model decisions, itinerary arithmetic, cost arithmetic, live place coverage, or Qwen quality. Those remain S3/integration evidence. G3 fixture seed has a ready four-member plan calculated by Backend hashing, then fixed needs_input drafts; it is not a complete live four-person planning scenario.

S1 FE HEAD fee36dd8df43d93ad6d2b8af51ef4523c9af7402 was inspected and merged for G3; node --test frontend/tests/*.test.js => 27 passed. Further S1 follow-up commits must be collected before final integration. S3 is still running. Push/PR/develop integration is pending final gates and is owned only by S2.
