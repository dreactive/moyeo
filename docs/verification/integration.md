# Integration verification — S2

Date: 2026-11-18, Asia/Seoul. This report separates independent, fixture/fake integration, and live/model evidence.

## Workspaces and versions

- Common base: 20db9c11b2f8a6bdbfa1824720ca9aa502fe71a3.
- S2 integration: C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/.worktrees/trip-s2-be, branch work/be.
- S1 verified handoff: work/fe 615172b (including c01f8c1 and four common-basis follow-up commits), merged into S2. Frontend source remains owned by S1.
- S3 core handoff: b7c2a6b explicitly approved and merged for G2. Final additional SHA and GPU release remain pending. No uncommitted AI source has been integrated.
- Source checkout, submission package/PDFs, ignored weights, personal AGENTS/skill and existing user keys remain preserved.

## Gates

| Gate | Actual mode and command | Observed result | Status |
|---|---|---|---|
| G1 FE | node --test frontend/tests/*.test.js | 40 passed, no failures; includes request/target race, first SSE recovery, edited-field PATCH, official snapshot colors. | PASS independent fixture |
| G1 BE | backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q | 111 passed, 3 integration cases deselected, one Starlette httpx deprecation warning. Fresh subprocess AI/torch import blocking and cold app import passed. | PASS independent fixture |
| G1 AI | S2 integration venv, ai/tests at 5f2bc5b | 111 passed in 3.12 seconds; synthetic replay 18/18; final model/docs handoff pending. | PASS core independent fake/fixture |
| G2 BE/AI | Real LocalAIBridge + S3 runtime fake/fixture | 3 integration scenarios pass: real JSON apply/observations/trace; four HTTP accounts from empty room through menu/car inputs, ready 130000 and unanimous confirmation; declared late-day existing plan through owner deadline, conflict, drop, recalculation, new unanimous target and immutable history. | PASS fake/fixture runtime |
| G3 FE/BE | http://127.0.0.1:8000, actual FastAPI + SQLite + FixtureAgentPort | Four cookie logins, 3/4 pending and 4/4 same-target confirmation, one POST delivered over real SSE to the three other clients, dev token gate, public JS key only in HTML. | PASS HTTP fixture |
| G3 UI | Parent IAB observation | Login, invitation, pinned review/confirmed target and four votes, place/menu/evidence details, two actual Kakao SDK map components observed. S1 follow-up fixes integrated; final G3 UI recheck below passed. | PASS UI fixture; latest basis invalidation separately FE 40-test verified |
| G4 | local_qwen/live providers/four-person planning | Integration environment prepared only. No completed S2 Qwen/live four-person run yet. | NOT PASSED |

Local reproducible transport scripts/output: backend/.artifacts/g3_server.py, g3_http.py, independent-tests.txt, frontend-tests.txt. Artifacts are intentionally ignored. Synthetic demo accounts and credentials are local test setup; they are not user accounts on an external service. The ready seed is explicitly a fixture plan hashed by Backend build_plan; subsequent port output is the fixed needs_input example. HTTP success is not a claim of natural-language planning.

## Review and environment decisions

- Parent performed independent fresh Backend/FE review. Reproduced findings have RED→GREEN regressions: concurrent messages/status; join events/recent-50; immutable review vs new draft conflict/evidence; condition kind changes; no-draft price changes; queued and in-flight stale jobs; registered-but-wrong response identity; menu target validation; trace step ordering; cold import cycle; bounded processed-message batches.
- New alternative-only evidence does not invalidate a frozen review. Actual evidence changes used by that review invalidate it even if plan_draft is null.
- AI task recent_messages is a bounded chronological batch of unprocessed messages, with the existing structured room state. Backend stores the accepted last_processed_message_id atomically, drains backlog, and avoids extracting the same source again. No new JSON contract field was added.
- Windows Store Python aliases could not start. Backend independent venv uses Python 3.13.9 from Anaconda. Managed sandbox async/DNS behavior required approved execution; failures were not reported as tests passing.
- G4 uses a separate Python 3.12.14 environment at backend/.data/integration-venv. It reads the previous project's ML site-packages through a local .pth, without modifying that environment. Available packages: torch 2.14.1+cu126, transformers 4.57.6, peft 0.21.3, accelerate 1.16.0, safetensors 0.8.0. Backend + AI non-model dependencies were installed only in this integration venv.
- Runtime env_file is the absolute original project .env. DEV_TOKEN was generated only when absent; values were never printed or committed. Only KAKAO_JAVASCRIPT_KEY reaches browser HTML. Provider, Mobility, REST and developer secrets do not.

## Live evidence pending consolidation

Parent/S3 reported successful Kakao Local/Mobility/SDK connectivity and Apify place coverage. These are external evidence handoffs, not a substitute for S2's complete live planning run. S3's pure base-model extraction initially failed validation; code-assisted extraction must be reported separately from actual LoRA action selection. No pricing, cost, itinerary or extraction algorithm is duplicated in Backend.

## Delivery

Original develop and remote refs were unchanged during independent work. Only S2 will integrate verified final SHAs, run final checks, safely update original develop, push without force, and open master <- develop PR without merging. Remote refs were still empty on the latest read. PR creation and final push remain pending the integrated gates.

## G3 final UI recheck (2026-11-18)

Parent IAB rechecked the fresh room-g3-2ab86e3d after restarting with a new isolated SQLite file and unique room/invite IDs. Observed: actual cookie login/join; current draft separate from pinned review revision2; review==confirmed same actual content hash and 4/4 votes; both same-version fixture items green; place details/source text; two actual Kakao SDK tile/marker/polyline map components. Screenshot: C:/Users/user/.codex/visualizations/2026/11/17/01a1e9f0-734d-7000-8d80-dc48c5f02a61/g3-integration.jpg. This is fixture places/prices plus actual SDK/HTTP integration, not live planning. G3 UI is PASS.

An earlier test bootstrap reseeded room state while retaining old events in the same test DB. That invalid fixture could move the browser cursor ahead of the reseeded snapshot. The bootstrap now creates a fresh DB and unique room ID for every run; the FE stale-response guards were preserved. HTTP/SSE and UI were rerun successfully on the consistent fresh fixture. Real user/source data was not reset.


## G2 complete fake/fixture path

Command: backend/.data/integration-venv/Scripts/python.exe -X utf8 -m pytest -c backend/pytest.ini backend/tests/test_end_to_end.py -q -m integration => **3 passed**, one Starlette warning, 1.50 seconds. Tests use the actual S3 runtime and registered tools. They do not load Torch or claim live facts.

The first scenario verifies JSON application, room observations, human-message isolation and actual fake decision/state_applied traces. The second creates four HTTP accounts and a new room, extracts the first place, counts three unique supporters with a repeated utterance, resolves the menu and explicitly declared fuel/parking/toll cost, calculates a ready 130000 KRW plan and requires four equal targets before green. The third starts from a declared existing 17:00 second-day visit, confirms its baseline, adds an owner-only 16:00 deadline, obtains a blocking conflict, selects the stored drop option, recalculates, and collects a new unanimous target while retaining both immutable confirmed snapshots.

The late-visit data is a Backend-owned fictional fixture. Its second-day hours are explicitly declared in backend/tests/fixtures/README.md and remain mode=fixture; original AI/common examples were not edited. The dropped-only late-visit case checks selection/revision/history; the separate empty-room case checks an included item's green state.

Integration found and fixed generated question identity drift: question IDs derived from a temporary client_ref are normalized together with target_ref only when they exactly match the generated question pattern. Custom opaque/support-source IDs remain unchanged. This prevents the original and resolved IDs from leaving duplicate open menu cards after a valid answer. Unit RED→GREEN and complete four-person HTTP flow verify the fix.


## Reviewed AI readiness/matching integration

Merged parent-reviewed 5f2bc5b into work/be (merge e38a440). S2 independently ran AI light suite **111 passed, 3.12s** and `python -m ai.eval.replay --model fake --providers fixture --cases ai/eval/cases.jsonl --output backend/.artifacts/ai-replay-final.json` => **18/18 passed**. No GPU was used by S2 in these checks.

The stronger AI coverage gate exposed an inconsistent Backend-owned late-visit test seed: its selected_item_ids still contained a removed first-day visit. The test input now declares exactly its remaining late visit and corresponding item snapshot (3e86b3a). The actual full fake/fixture integration suite then passed again: **3 passed, 1.66s**, one Starlette warning. No product completeness check was weakened.

Parent independently replayed actual Kakao/recorded-live Apify matches for three businesses against the corrected canonical road/address matching; different-business negative cases still reject. This uses existing responses, not new Apify calls. G4 remains pending the final AI run and GPU release.


## Final AI handoff integrated

AI8c55e36 is merged at S2 a8287bb. S2 integration venv independently executed **113 AI tests passed, 2.86s**, **18/18 fake/fixture replay cases**, and **3 G2 integration tests passed, 1.64s** (one Starlette warning). S1 final615172b/FE40 remains included. Final AI README resolves the previous pending root link.

S3 actual component run at a9154f1, clean start, completed normally in590.215s (model load5.3098s):5 real tool decisions,3 fresh Kakao route observations, ready134000 KRW/unknown0/conflicts0. All5 literal assertions, finite argmax and selected arguments matched actual calls. The later98117d4 rejects fractional sub-won arithmetic and has113-test regression; the live result is not relabelled as that later SHA. The initial unbounded-map-context failure and ~9m50s final latency remain documented. Product geometry is preserved. model_context removes duplicate geometry from generation/judge context; scored candidate strings and executed tool arguments still retain their full route geometry. This remains a performance optimization candidate, not a reason to relabel current correctness evidence.

S3 confirmed model/process shutdown and GPU release before S2 started G4. G4 uses a8287bb clean product code, one runtime, actual uvicorn TCP four password logins, unchanged recorded-live Apify details (Aqua Planet/Jinnamgwan), explicit synthetic anchor/menu quantity/visit/fixed-cost inputs, and fresh live Kakao routes. Mode labels do not claim blank-room free-form search quality. Actual G4 outcome follows below when complete.
