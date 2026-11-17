# S3 AI verification — 2026-11-18 KST

Scope: A0–A5, docs/superpowers/plans/2026-11-18-ai.md. Baseline
20db9c11b2f8a6bdbfa1824720ca9aa502fe71a3, branch work/ai. Only ai/** and this
document are changed. Common contract v0.2 remains unchanged. S2 owns integration,
develop push, PR and the global checklist. Standalone AI proof is separate from G4.

## Workspace and rulings

- Worktree: C:/Users/user/.codex/visualizations/2026/11/17/01a1ea46-36e4-7542-b516-bcd5bda0f153/trip-s3-ai.
- Native create_worktree failed twice “Could not find a Git repository at sourceRoot”. Git confirmed the repository/baseline. Manual worktree creation succeeded with expanded permission; native attach rejected unmanaged metadata. Coordinator explicitly approved continued use of this exact isolated worktree. Every shell uses explicit cwd. Source checkout has no S3 product writes.
- Keep the ledger inside owned paths; shared plans/contracts/checklist are read-only. The approved implementation request supersedes the plan's original “not executed” status. AGENTS.md/.local skills remain ignored/unstaged. No history rewrite.
- Small-commit target: about300 executable characters per behavior, focused tests and explicit paths. 75133d7 is a recorded larger exception: the calculation precondition gate and independent final-assembly coverage had to close the same false-ready defect at both boundaries. Most other changes follow small behavior commits; no claim every commit meets300.
- Minimal asyncio.sleep(0) hangs in this Windows restricted shell and succeeds in expanded permission (~0.5s). Async tests/CLI/model/provider runs use expanded permission; application asyncio was not replaced. One approval-review timeout was retried once successfully.
- New ai/.venv uses Python3.12.14. Existing ML site-packages are referenced read-only through a .pth file inside this new venv only. The old environment was not changed. README gives exact paths/dependencies/commands.

## A0: independent runtime

create_runtime(config) supplies async run/execute_tool/aclose. No Backend,
FastAPI or SQLite imports are needed. Fake mode needs no Torch/GPU/credentials.
One model instance is serialized off the event loop; each task/tool restores its
own room context and observed references/anchors. Closing is idempotent.
Canonical field tests preserve run_id/room_id/base_versions. AI returns proposals,
observations and calculations; official confirmations/IDs/versions/hash and
state_applied belong to S2. Five registered tool signatures match v0.2.

Goal mapping: new_message/message_created/remaining_messages extract and skip
lookups for chitchat/repeated support without a new place. A named new place can
start a first plan. manual_replan recalculates derived outputs. chat/messages/
extract are extraction-only. Generic failures use diagnostic termination and
needs_input, without inventing a constraint_value question with target=null.

## A1: actual providers and model

Selected Kakao Local + Mobility and Apify Naver-map details. Source .env is read
only, with no credential values logged/copied to models or artifacts. Apify
succeeded, so fallback was unnecessary (C02 not applicable). Jeonnam/TourAPI keys
were absent. Requests exclude reviews and cap results at5. The initial probe's
schema key was corrected to documented maxResultsPerKeyword before follow-up.

Actual source observations, Nov18 01:53–02:16 KST, visiting dates Nov21–22:

| Place | Positive price example KRW | Observed daily hours |
|---|---:|---|
| 덕수파스타 여수 직영점 | 17,900 | 11–16,17:10–21:30 |
| 진남관생선구이 이순신광장점 | 15,000 | 10–15,17–21 |
| 여수게장 황소게장 | 35,000 | 08–20:20 |
| 서울해장국 | 11,000 | 05–23 |
| 여수 명동게장 | 35,000 | 07–21 |
| 모이핀 오션점 (cafe) | 9,300 | 09–20:30 |
| 아쿠아플라넷 여수 | 37,900 | 09:30–19 |
| 여수 유월드 루지 테마파크 | 25,900 | 10–18 |
| 여수해상케이블카 | 17,000 | unknown; not counted as usable tourist hours |

Evidence: ignored ai/.artifacts/apify-live-probe.json, apify-tourists.json,
apify-additional.json. First probe SUCCEEDED in27.4s. Stored summaries are
normalized place/menu/hour evidence, with no review/image data or complete
source response. Source update dates/serving units remain null when unknown.

Recorded live Kakao+Apify matching replay makes zero additional API calls:
덕수파스타6.4m, 모이핀1.6m, 서울해장국1.7m match uniquely; 황소게장 vs
황소식당3.6m is rejected despite proximity. Municipality, optional 읍/면, road,
building number, business name and coordinates are compared; province aliases
and trailing floor/shop annotations do not break joins. Original addresses stay
unchanged. Evidence: matching-replay.json. This is recorded-live replay, not a
new live API call or fixture sample.

Public-runtime fake/live provider-only probe searched 여수엑스포역/오동도/여수시청
and queried Nov21 09:00 future driving:3,568m/461s/toll0, evidence
kakao:route:77c853633bfd6aa60a81. kakao-runtime.json explicitly labels fake model;
this proves providers, not Qwen. Future timestamps use Mobility future endpoint;
route identity includes departure and actual endpoint coordinates.

Actual model: local Qwen/Qwen2.5-1.5B-Instruct plus supplied judge LoRA. Base
generation disables adapter; judge enables it and calls original submission
judge_scores with actual candidate counts1/2/5 (~0.5/0.95/2.4s), finite scores.
Load~5.1–5.6s; short extraction~0.8–3.0s; initial peak~3,584MiB on RTX4070 12GB.

Free-form extraction quality FAILED: missing source IDs or empty arrays in real
probes. This is not a model-quality pass. Explicitly approved narrow assistance
preserves sources for budget/return/self-support/place mentions; every trace
labels extraction_mode=rule-assisted. Ambiguous targets stay questions. Code
offers grounded independent choices; actual finite judge argmax selects actions,
with no candidate0 fallback or forced four choices. qwen-probe.json and
qwen-runtime.json are earlier exploratory evidence, not final-code evaluations.

## A2–A4: behavior and review

- Costs distinguish paid/plan/null, owner budgets, shared remainder and per-person-null-owner. Shared101 ->26/25/25/25 sorted IDs. Budget200k/paid80k/future70k ->remaining120k/planned balance50k. Unknown serving units need explicit quantity/scope; fuel/parking need user input. Toll is separate unless explicitly included. No invented zero prices.
- Schedule uses actual route seconds, exact departures and ordered repeated route pairs. Last-day return, closures/breaks and missing hours/anchors block ready. Coordinate changes invalidate cached routes. Stays default60; cafe40 currently requires an explicit duration answer.
- Recent20 plus structured state/answers preserve sources and owner corrections. No proxy support or official confirmations. First question-form place mention creates proposal without support. Opaque support question ID: question:support_target:{support|oppose|withdraw}:{source_message_id}; suffix may contain colons, owner=original author, target=null until resolved. S2 agreed this format.
- Stale selections do not execute effects. Drop/reorder/replace recalculate. Hard constraints are never silently relaxed; unsupported hard keys and new same-run hard proposals block ready pending owner confirmation.
- Tool arguments must equal grounded canonical calculations. Invalid score length/NaN/empty candidates never select candidate0. Max20 actual actions; failure/limit remains needs_input. Calculation gate and independent final assembly require complete selected/new visit coverage and current observations.
- Trace links run/step/call, candidates/scores, normalized results and timings, redacts credentials/private reasoning. Product observations survive disabled trace. Runtime tests cover model reuse/serialized close and two-room isolation.
- Readonly final review found two P1 defects: unresolved items could yield an empty ready plan; a new hard proposal could leave ready status. Fixed75133d7/d26c28a with failing→passing tests in test_readiness.py. Parent's earlier findings on triggers/question targets/first-plan/question-form mentions have regression tests. No Critical/Important finding remains from that review's fix pass; no recursive re-review.

## A5: commands and evidence

Run from this worktree with ./ai/.venv/Scripts/python.exe. Async commands use the
expanded shell. Fake results and real model/provider results remain separate.

| Command/evidence | Mode/revision | Result |
|---|---|---|
| -m pytest -c ai/pytest.ini ai/tests -q -m "not live_model and not live_provider" | offline/98117d4 |113 passed, 2.69s|
| -m ai.eval.replay --model fake --providers fixture --cases ai/eval/cases.jsonl --output ai/.artifacts/eval-offline.json |fake/fixture,5910514 clean|18/18passed|
| ai/.artifacts/final_static_checks.py |recorded-live/no API|3correct joins; wrong business rejected; all hashes preserved|
| eval-live-context-limit.json |local_qwen/live,5910514 clean|ready assertions failed; first route then input27,459>24,000token limit|
| eval-live.json |local_qwen/live,a9154f1 clean|1/1 passed; done/ready, total134,000, unknown0, conflicts0;590.215s|

18 cases cover chitchat/repeat, ambiguous support, correction, question mention,
minority hard budget, last-day16:00 return, holiday, overbudget, null price,
other branch, stale selection, answered inputs, restored observations, missing
anchor, first plan, unsupported transport and selected drop. Literal paths,
calls, decisions, timing and mode labels are asserted; input patching does not
simulate Backend confirmations/persistence. Missing models/keys are not passes.

Live case uses observed 서울해장국 details plus synthetic explicit input:4adults,
one11,000-KRW meal each, lodging80,000, fuel/parking10,000. City-hall coordinates
are a synthetic lodging anchor, not a reservation. Expected total134,000 with
zero extra toll. This component test is not an empty-room product demonstration.
README contains the public CLI equivalent. final_live_eval.py only adds actual
CUDA peak/after-close and installed-version measurements to the same evaluator.

First final live failure was diagnosed from saved observations without new API:
27,459 post-route prompt tokens. Fix609913d/a9154f1 excludes only polyline arrays
from generation/judge views while preserving full product geometry and all
route seconds/tolls/evidence. Red→green regression verified. Input24,000/output
1536 limits remain; no judge score/choice/arguments were forced.

Final arithmetic boundary fix 98117d4 rejects fractional-won subtotals rather than
silently truncating them; integral subtotals with fractional quantities remain
valid. Its focused red→green and full113-test regression passed. The running
live evaluation started from clean a9154f1 before this isolated cost guard;
its integer-quantity input is unchanged. No additional model run is needed to
verify this Decimal-only boundary.

An independent subprocess blocked torch/transformers/peft/backend/fastapi/sqlite3
imports and successfully ran/closed fake/fixture runtime. Evidence command:
ai/.artifacts/verify_core_imports.py. Live evaluations execute directly; no
unexecuted pytest marker or skipped live test is counted as a pass.

## C01–C47 evidence boundaries

| Checklist | S3 proof / integration boundary |
|---|---|
|C01–C03|Actual restaurants5/cafe1/tourist2 usable hours+prices;3independent business joins; fallback not applicable; cablecar hours unknown|
|C04–C05|Actual base/LoRA mechanics and modes; same JSON fake/local; extraction quality failure retained|
|C09–C12,C15–C16|test_context_extraction/assistance/questions/runtime_contract:owner/source/support/zero redundant lookups; UI/history is S1/S2|
|C13–C14,C17–C18|Question-form proposal/support semantics only; colors/official confirmations are S1/S2|
|C19–C21,C32|test_itinerary_costs/cost_inputs/selection/readiness:conflicts/effects/recalculation/no false ready; versions/display are S2/S1|
|C25,C28–C31,C33|Actual routes/provider evidence+matching; code hours/cost/null/units/paid calculations; full live run separately labelled|
|C34–C35|Actual variable-candidate judge traces and changed route context; failed run is not a completion pass|
|C36–C37,C47|test_runner/trace/tool_context/model_backend:limits/errors/unsupported/redaction/observations/room isolation; applied versions belong to S2|
|C39,C41|18fake/fixture cases and separate local/live; standalone AI without Backend; S1/S2 independence needs their records|
|C42–C44|README paths/dependencies/commands/gaps; submission9+PDF2 unchanged; combined startup is S2|
|C45–C46|Answered anchors/menu/duration/owner and exact200k/80k/70k balance tests; input cards/API are S1/S2|
|C06–C08,C22–C24,C26–C27,C38,C40|Outside S3:login/SSE/private views/review snapshots/versioned confirmations/developer endpoint/full4user product demonstration require S1/S2 G4|

## Preservation and handoff

preservation-before.json/after.json match9 original submission files including
adapter weights. Both PDFs in source/worktree match baseline20db9c1 Git blobs.
PDF baseline is reconstructed from Git, not misrepresented as an observed
before-run hash. No submission/TeamPredictor edit. Ignored artifacts/venv are not
staged; required local summaries contain no credentials.

Remaining limitations: free extraction quality unsolved and assistance labelled;
unknown serving units/source update dates stay null; region-only conversation
does not discover a complete plan; cafe40needs explicit duration because PlaceRef
has no reliable category; unsupported hard rules need owner input. Standalone
ready does not prove persistence/official confirmations/C40.

S2 already validated core through b7c2a6b; coordinator reported later111tests and
G2 scenarios. These are not claimed as independent S3 product execution. Final
delta b7c2a6b..finalHEAD; full range20db9c1..finalHEAD. Model-evaluated head a9154f1
has120commits from baseline; arithmetic guard98117d4 and evidence docs follow. Local
ai/.artifacts/commits.txt records full log. S3 does no push/PR per explicit S2
ownership; keep worktree/branch.

## Final actual run and resource handoff

The final run completed normally before the announced ten-minute cap; it was
not interrupted. Code a9154f11731b16d02c87fa164dd9ef6118f2b5ff, git_dirty=false,
Python3.12.14. Local base/LoRA load5.3098s; case584.2552s; total590.215s.
All five literal assertions passed: done, ready, total134,000 KRW, unknown0,
conflicts0. This is the component test described above, not G4 product approval.

Actual selected sequence, verified finite argmax over complete score arrays:

| Step | Candidate count | Selected index/tool | Scores |
|---|---:|---|---|
|1|3|0 get_car_route|2.7964,-3.4674,-5.2856|
|2|3|0 get_car_route|2.4521,-1.7811,-5.3520|
|3|2|0 get_car_route|2.2660,-4.5816|
|4|3|1 calculate_costs|-1.8972,1.7640,-4.5180|
|5|2|0 build_itinerary|-2.1758,-4.2196|

Cost was selected before itinerary from independent available alternatives;
this is not a fixed tool-order claim. All three returned route observations have
Kakao evidence and nonempty real geometry: origin→서울해장국 2,524m/454s;
restaurant→lodging 8,614m/1,317s at Nov21 11:07:34; lodging→destination
9,716m/1,155s at Nov22 10:00. Toll0 each. The next departure used the preceding
real duration. eval-live-audit.json was independently generated from the report,
asserting finite scores/true argmax, three live route IDs and preserved geometry.

CUDA peak allocated8,134.03MiB; after awaited aclose16.25MiB, then process exit.
Installed torch2.14.1+cu126/transformers4.57.6/peft0.21.3/accelerate1.16.0/
safetensors0.8.0. Nov18 around03:54 KST: both probe PIDs48148/48308 absent;
nvidia-smi shows449MiB total desktop memory and no Python compute process.
S3 GPU/live-provider exclusivity has ended; S2 may start G4. No paid API or model
rerun will be started by S3 during handoff. Full live-input latency (~9m50s) is a
material remaining performance limitation, despite the correctness pass.

The independent model report records its actual start SHA a9154f1. Subsequent
98117d4 only rejects sub-won arithmetic (113-test regression); remaining changes
are documentation. Results are not relabelled as a run of a later SHA.
