# Integration verification — S2

Date: 2026-11-18, Asia/Seoul. Local implementation and G1–G4 are verified. Remote push/PR is a separate delivery result; local gates do not imply publication.

## Versions and ownership

- Common base: 20db9c11b2f8a6bdbfa1824720ca9aa502fe71a3.
- Integration: C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/.worktrees/trip-s2-be, work/be.
- Final S1 handoff615172b and S3 handoff8c55e36 are merged. FE/AI changes stayed in their owned paths; S2 owns Backend/common integration.
- G4 executed clean product SHA a8287bbc4f0d56a45ca8c145a670e9be798c90d9, including final AI arithmetic guard. Subsequent changes are documentation. No uncommitted AI source was integrated.
- API/JSON contract v0.2 fields/enums and examples remain unchanged.

## Gates and executed commands

| Gate | Mode / command from repository root | Observed result |
|---|---|---|
| G1 FE | node --test frontend/tests/*.test.js | 40 passed, no failures; parent independently reran40. |
| G1 BE | backend/.venv/Scripts/python.exe -X utf8 -m pytest -c backend/pytest.ini backend/tests -q | 111 passed, 3 integration cases deselected; one Starlette httpx deprecation warning. Parent independently reran111 with Python3.12. Fresh subprocess blocks ai/torch imports and cold app/observation-first imports pass. |
| G1 AI | backend/.data/integration-venv/Scripts/python.exe -X utf8 -m pytest -c ai/pytest.ini ai/tests -q -m "not live_model and not live_provider" | 113 passed in2.86s; parent independently113. |
| AI replay | same integration Python -m ai.eval.replay --model fake --providers fixture --cases ai/eval/cases.jsonl --output backend/.artifacts/ai-replay-final.json | 18/18 fake/fixture cases; separate from actual-model quality. |
| G2 | same Python -m pytest -c backend/pytest.ini backend/tests/test_end_to_end.py -q -m integration | 3 passed in1.64s, actual LocalAIBridge/S3 runtime fake/fixture; one Starlette warning. |
| G3 | actual FastAPI TCP/SQLite/FixtureAgentPort + parent IAB | Four password/cookie clients, 3/4 pending vs4/4 confirmed, POST→three other SSE clients, token gate, public JS key only in HTML; actual two Kakao SDK maps and source/details UI. |
| G4 | actual uvicorn TCP + local_qwen + fresh live Kakao / recorded-live Apify | PASS full owner-condition→conflict→actual FE alternative→recalculation→new unanimous target, including final actual FE green/maps/costs. Details below. |

Independent Backend uses no AI/ML dependencies. The separate Python3.12.14 integration venv reads existing ML site-packages through its own .pth without modifying the old environment. Observed torch2.14.1+cu126, transformers4.57.6, peft0.21.3, accelerate1.16.0, safetensors0.8.0. Windows Store Python aliases failed; Backend-only venv used Anaconda Python3.13.9. Managed sandbox asyncio/DNS needed approved execution, not application workarounds.

## G2 and G3 boundaries

G2 tests actual JSON application/observations/trace and human-message isolation; a fresh room with four HTTP registrations through named-place proposal/three unique supporters/menu+explicit car input/ready130000/whole-target confirmation; and a declared second-day17:00 fixture visit through owner16:00 deadline, stored conflict selection, recalculation and two immutable confirmed snapshots. The late fixture is explicitly fictional (backend/tests/fixtures/README.md). It is not live coverage.

G2 found temporary question identity drift: generated question IDs are resolved with temporary target refs only for the exact generated pattern; opaque/support-source IDs remain unchanged. Unit RED→GREEN and full menu-answer flow pass. The newer AI completeness gate also exposed an inconsistent test seed (removed visit still selected); 3e86b3a corrected the declaration without weakening product validation.

G3 initially reseeded state while retaining events; the bootstrap now uses a new SQLite file/room ID for each run. Rerun HTTP/SSE and IAB passed on room-g3-2ab86e3d. Evidence: parent visualization directory g3-integration.jpg. No real user/source data was reset. FE615172b additionally has40 regressions for stale responses, concurrent form edits, first SSE recovery and version-aware official colors.

## G4 inputs and provenance

Command: backend/.data/integration-venv/Scripts/python.exe -X utf8 backend/.artifacts/g4_live.py. Ignored local inputs/results: g4-place-details.json, g4-live-report.json, g4-audit.json and g4-live-074d42ee.sqlite3. These are local evidence, not committed provider datasets.

- One actual Qwen base/current judge LoRA lifespan; four password logins into a declared existing four-person room and two-day itinerary. This is not a blank-room free-form search-quality claim.
- Unchanged S3 authenticated Apify normalized observations: Aqua Planet ticket37900 and Jinnamgwan meal15000, actual record IDs/URLs/visit-day opening intervals. Provider update dates/serving basis remain unknown where absent. No new Apify collection.
- Explicit synthetic user inputs: anchor coordinates, day1 Aqua14:00/day2 restaurant17:00,60-minute stays, quantity1 per person, shared paid lodging80000, unpaid car10000 including fuel/parking/tolls, per-person budget200000. These are inputs, not provider facts.
- Five fresh Kakao future-route HTTP requests, all200. Final itinerary legs exactly equal actual normalized observations, including16m/2s/2 API vertices,1943m/421s/62 vertices,1985m/348s/63 vertices. No renderer-created straight road substitute. The short first leg genuinely has two API vertices; equality with returned observations, not an arbitrary >2-point threshold, is the audit criterion.

## G4 observed sequence and independent audit

| Phase | Seconds from start | Result |
|---|---:|---|
| Baseline |573.802|ready301600; 3/4 remains unconfirmed, fourth equal target confirms. |
| u4 message |575.139|return_by16:00 needs_owner_confirmation; u1 confirm403, u4 confirm200; old confirmed snapshot retained. |
| Owner-confirmed calculation |1195.533|blocking time conflict for item-b; current confirmation disabled; old confirmed revision2 retained. |
| Actual FE visit-exclusion selection |1718.944|new route, cost and itinerary; ready241600, no conflicts, zero inherited confirmations, new target. |
| New unanimous confirmation |1719.095|four equal targets, included Aqua green, excluded restaurant not green; immutable history301600 then241600. |

PASS at1719.172s (28m39s); model load7.259s, generation287.701s, judge1371.773s. There are11 actual selected decisions, all finite score argmax, and11 selected tool_name/arguments exactly match executed calls. Four runtime traces have state_applied. Human chat contains only the actual u4 message; AI never posted human chat. SQLite independent read confirms both historical snapshots exactly match their originals.

Parent independently checked the actual developer endpoint: no token403, room cookie+token200, no actual .env key/DEV_TOKEN values in trace; all11 decisions and arguments match. Actual IAB selected the stored '방문 제외' option; no HTTP substitute selection was used. Final IAB observed revision4 review==confirmed/4of4, Aqua green, excluded restaurant yellow candidate, no blocking conflict, total241600/per-person60400/paid20000/planned balance139600, observed37900/source and both maps.

Final screenshots: C:/Users/user/.codex/visualizations/2026/11/17/01a1e9f0-734d-7000-8d80-dc48c5f02a61/g4-conflict.jpg and g4-confirmed-full.jpg. The cropped g4-confirmed.jpg is not the final full-screen evidence.

## Shutdown verification

The first G4 harness waited30s for an unbounded uvicorn shutdown while an IAB SSE remained open, then its daemon process exited. Its original report honestly retains server_thread_stopped=false/runtime_closed=false; process exit returned GPU memory. This is not relabelled as awaited aclose.

A separate actual-Qwen lifecycle probe (g4_shutdown_probe.py/result g4-shutdown-probe.json) held an SSE open with timeout_graceful_shutdown=2: server thread stopped=true, runtime_closed=true, aclose calls1, shutdown2.328s/total11.237s, GPU allocated after close0. No planning inference/provider calls. README uvicorn commands now specify --timeout-graceful-shutdown 5. The probe had no active GPU inference; an active serialized model operation may still need to finish before close acquires its lock.

## Limits, reviews and preservation

- Actual live latency is material and unresolved. model_context removes duplicate geometry from generation/judge context; scored candidate strings and executed arguments still retain full route geometry. This is a later performance optimization candidate, not a changed correctness claim.
- Free-form small-model extraction initially failed. Explicit source-preserving rule assistance is labelled; region-only conversation does not discover a complete plan. Unsupported hard rules require owner input; unknown prices/serving basis/provider dates remain unknown.
- C07 has actual POST→three independent SSE clients and actual FE behavior, but three browser screens simultaneously operated as different people were not observed. The checklist keeps that manual display scope partial.
- Parent performed independent fresh FE/BE/AI review. Reproduced corrections have regression evidence: identity/base/atomic application, bounded accepted-message cursor/backlog, owner conditions/question targets, immutable review vs draft/evidence, cold import, source/trace boundaries and FE basis/version races. Backend has no duplicate AI itinerary/cost/NLP algorithm.
- SQLite persists accounts/sessions/room/events/run provenance/immutable confirmations. Observations and sanitized trace are separate room-scoped process memory, so restart needs new observations. Keep one worker.
- Parent checked original submission9 files (including adapter), PDF2 and baseline diffs unchanged; personal AGENTS/.local/.planning/.env/weights are excluded. No credential values were printed/committed. Only the public Kakao JS key reaches HTML. Native worktree discovery failed; approved isolated manual worktrees preserved original develop until final handoff.

## Delivery

S2 performs the safe fast-forward of original develop from the verified work/be tree, then a non-force develop push and master<-develop PR attempt without merging. Remote outcome and exact delivered HEAD are recorded in the final handoff; local G1–G4 results alone do not imply remote refs/PR creation.
