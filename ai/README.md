# Independent travel-agent runtime

AI owns Python calculations, model inference and provider observations. No server,
FastAPI, SQLite, frontend or Backend imports are required. All public values are
JSON dictionaries/lists/scalars. Common API v0.2 remains unchanged.

## Install and run

From the repository root, using Python 3.12:

```powershell
python -m venv ai/.venv
./ai/.venv/Scripts/python.exe -m pip install -r ai/requirements.txt
./ai/.venv/Scripts/python.exe -m pytest -c ai/pytest.ini ai/tests -q -m "not live_model and not live_provider"
./ai/.venv/Scripts/python.exe -m ai.cli run --task ai/fixtures/agent-task.json --model fake --providers fixture --output ai/.artifacts/result.json
```

Windows desktop sandbox note: even an empty asyncio loop hung in the restricted
shell here. The same tests/CLI succeeded in an approved expanded-permission shell.
Do not replace asyncio to work around that host issue.

The default fake/fixture path needs no Torch, GPU, credentials or external network.
Fixture places and routes are explicitly synthetic; mode labels must be retained.
Unknown car/entry/menu costs remain null and need input.

## Backend connection

```python
from ai.runtime import create_runtime

runtime = create_runtime({
    "model_backend": "fake",       # fake | local_qwen
    "provider_mode": "fixture",    # fixture | live
    "base_model_path": None,
    "adapter_path": None,
    "env_file": None,
})
result = await runtime.run(task, emit_trace)  # emit_trace may be None
detail = await runtime.execute_tool("get_place_details", {"place_ref": ref}, {
    "room_id": room_id, "config": config, "observations": observations,
})
await runtime.aclose()
```

Create once per application lifespan. Model operations use one lock and run outside
the asyncio event loop. Tools restore a separate context for every task/room.
Closing is idempotent. Backend owns IDs, versions, official confirmations,
atomic state application and state_applied trace events.

Result contains proposals, calculated plan_draft, new tool observations,
questions/conflicts, completion and original run_id/room_id/base_versions.
plan_draft contains only selected_item_ids/days/cost/validation/blocking_conflict_ids.
Trace is optional diagnostics; observations are the product data boundary.

Backend goal mapping: `new_message` (also `message_created`/`remaining_messages`)
extracts new proposals; chitchat or repeated support without a new place performs
no lookup. A new named place can start a first plan. `manual_replan` forces fresh
derived itinerary/cost calculations while reusing valid source observations.
`chat`/`messages`/`extract` are extraction-only. An unchanged, ready current plan
can be reused for other triggers. New hard proposals stay pending until their
owner confirms them through Backend. Generic failures end with `needs_input`
and diagnostic termination, without inventing a domain question target.

For a ready cost, users must select unknown menu quantity/scope, provide missing
anchors, and explicitly enter fuel/parking costs. A fixed `car` line describing
both 유류 and 주차 resolves those unknowns; observed tolls remain separate unless
the user explicitly includes 통행료 in that line. Paid lodging is an input cost,
not a verified reservation. Unknown prices/hours remain input blockers.

Question linking agreed with S2:
`question:support_target:{support|oppose|withdraw}:{source_message_id}`.
owner_id is the original author; target_ref stays null until resolved. The
source ID suffix is opaque (it may contain colons); split only the known prefix
and stance. AI creates no proxy votes.

## Model behavior and provenance

The local backend loads one supplied Qwen base and current judge LoRA.
Generation disables the adapter; scoring enables the judge and uses the original
submission.judge.judge_scores with any real candidate count. No TeamPredictor
choice-0 fallback or forced four-choice service behavior is used.

Free-form small-model extraction failed the initial real probes. Clear explicit
budget/return-time/self-support statements therefore also use source-preserving
code assistance. Trace labels this **rule-assisted**; this is not a model-quality
pass. Ambiguous targets remain questions and owner constraints are proposals.

Code offers grounded, independently available actions alongside generated model
actions (for example, first-day travel and the separate second-day return leg).
The judge's actual finite scores select an action, including asking for input.
Every result changes the next context/options; no code-selected first-candidate
fallback runs. Known duplicate queries are omitted. Maximum actual choices: 20.
Prices, participant budgets, route seconds, dates and KRW arithmetic come from
observations/user inputs and code; mismatching model arguments are rejected.
Fractional quantities are allowed only when their subtotal is an integer KRW
amount; sub-won results are rejected instead of silently truncated.
Base/judge inputs omit map polyline arrays; full geometry remains in returned
observations. The 24,000-token input guard still ends oversized requests safely.

## Live providers

Credentials are read from the explicit env_file without changing process
environment or exposing key values to models/trace. For this checkout, use:

`C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/.env`

Selected combination: Kakao Local + Mobility, and Apify Naver-map details.
Apify calls exclude reviews and cap each request at five places. Cross-provider
joins require a unique provider ID or matching address and coordinates; name
alone is insufficient. Unknown serving basis is not automatically one meal per
person. Source update dates stay null when unavailable. TourAPI/Jeonnam were not
selected because those credentials were absent; they are not silently simulated.

Primary references:
[Apify schema](https://apify.com/huggable_quote/naver-map-scraper/api/openapi),
[Kakao Local](https://developers.kakao.com/docs/ko/local/dev-guide),
[Kakao future routes](https://developers.kakaomobility.com/guide/navi-api/future.html).

## Local model setup used in this session

Optional packages are separate in requirements-local-qwen.txt.
Existing ML packages were reused read-only by adding their site-packages path
to a .pth file in this AI venv only. No existing project environment was changed.
Observed versions: Python 3.12.14, torch 2.14.1+cu126, transformers 4.57.6,
peft 0.21.3, accelerate 1.16.0, safetensors 0.8.0.

- Base: C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton/.local/models/Qwen2.5-1.5B-Instruct
- Adapter: C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/submission/weights/adapter_model.safetensors
- Adapter config: same directory, adapter_config.json
- Existing ML site-packages: C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton/.venv/Lib/site-packages
- This session Python: C:/Users/user/.codex/visualizations/2026/11/17/01a1ea46-36e4-7542-b516-bcd5bda0f153/trip-s3-ai/ai/.venv/Scripts/python.exe

Use a separate Backend integration venv with these optional packages or a
read-only site-packages reference; do not install Backend dependencies into
the existing ML venv. Only local weight files are loaded; no model downloads.

Real probe: base load ~5.1–5.6s, generation of the short extraction case
0.8–3.0s, judge candidate counts 1/2/5 ~0.5/0.95/2.4s. Peak allocated GPU
memory ~3584MiB on RTX4070 12GB. Extraction quality and mechanics are separate.
Full run/provider results and resource shutdown are recorded in
docs/verification/ai.md; ignored ai/.artifacts contains local evidence.

Final local_qwen/live component run (clean a9154f1) passed in 590.2s:
three real future driving calls plus cost/itinerary calculations, ready total
134,000 KRW with explicit synthetic user cost inputs. Actual judge scores chose
cost before itinerary. Peak CUDA allocation was 8,134MiB; after aclose 16.25MiB,
then the process exited. This long live-input latency is a current limitation;
the short mechanics timings above do not predict full-run latency.

## Reproduce evaluation

```powershell
./ai/.venv/Scripts/python.exe -m ai.eval.replay --model fake --providers fixture --cases ai/eval/cases.jsonl --output ai/.artifacts/eval-offline.json
./ai/.venv/Scripts/python.exe -m ai.eval.replay --model local_qwen --providers live --cases ai/.artifacts/live-cases.jsonl --output ai/.artifacts/eval-live.json --base-model-path C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton/.local/models/Qwen2.5-1.5B-Instruct --adapter-path C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/submission/weights --env-file C:/Users/user/Desktop/Competition/2026_AI_Agent_Hackaton2/.env
```

The fixed 18-case replay is portable. The ignored live case contains previously
observed restaurant details and explicit synthetic user inputs; it is a component
test, not a real booking or a full product session. It must be prepared again
with current source observations and future trip dates on another machine.
Reports include code SHA, dirty status, mode labels, actual decisions/scores,
tool observations and literal assertions. A missing model/key is not a pass.
Live calls can cost money; probe only the required small sample.

Current defaults use 60-minute stays where no duration is supplied. Category-free
PlaceRef does not identify cafes reliably; select 40 minutes through the
`visit_duration` answer for cafes. Region-only conversation without a named place
does not automatically discover a complete itinerary. Arbitrary hard conditions
outside supported budget/return rules require owner input and block readiness.
