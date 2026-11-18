# Independent travel-agent runtime

AI owns Python calculations, model inference and provider observations. No server,
FastAPI, SQLite, frontend or Backend imports are required. All public values are
JSON dictionaries/lists/scalars. This branch stops planning runs after generating
and validating action candidates; it does not score, select or execute them.

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

Result contains proposals, questions, completion and original run_id/room_id/base_versions.
Planning runs also return `candidates`, even with tracing disabled. Each candidate
contains action/reason/tool_name/arguments/source_message_ids/source_refs.
`plan_draft` stays null, new `observations` stay empty, and `completion` remains
`needs_input` because no plan has been calculated. Decision traces contain the
same candidates with `selected_index: null` and `scores: []`.
Explicit `runtime.execute_tool(...)` remains available to callers.

Backend goal mapping: `new_message` (also `message_created`/`remaining_messages`)
extracts new proposals; chitchat or repeated support without a new place performs
no lookup. A new named place generates search candidates. `manual_replan` and
other planning triggers produce one candidate batch from valid source observations;
they do not execute a loop or return a reused plan.
`chat`/`messages`/`extract` are extraction-only and omit `candidates`.
New hard proposals stay pending until their
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

The local backend retains the existing supplied Qwen base/adapter loading contract.
Generation disables the adapter. Service scoring methods and argmax selection
have been removed; the original submission package remains preserved separately.

Free-form small-model extraction failed the initial real probes. Clear explicit
budget/return-time/self-support statements therefore also use source-preserving
code assistance. Trace labels this **rule-assisted**; this is not a model-quality
pass. Ambiguous targets remain questions and owner constraints are proposals.

Code offers grounded, independently available actions alongside generated model
actions (for example, first-day travel and the separate second-day return leg).
All valid alternatives are returned without ranking or choosing a first candidate.
Known duplicate queries and invalid or already observed tool calls are omitted.
Prices, participant budgets, route seconds, dates and KRW arithmetic come from
observations/user inputs and code; mismatching model arguments are rejected.
Fractional quantities are allowed only when their subtotal is an integer KRW
amount; sub-won results are rejected instead of silently truncated.
Base-model inputs omit map polyline arrays. The 24,000-token input guard still
ends oversized requests safely.

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

Historical scoring-branch probe (not remeasured for this candidate-only branch):
base load ~5.1–5.6s, generation of the short extraction case
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

The fixed 18-case replay now checks candidate-only results, with zero automatic
tool calls and no plan draft. It does not verify end-to-end itinerary completion.
The ignored historical live case contains previously
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

## 스키마·근거 기반 추출 (로컬 Qwen)

`local_qwen`은 메시지별 `MessageFacts`를 Pydantic JSON Schema와 LM Format Enforcer로 생성한다. 모델이 장소명/조건 값을 추출하고, 코드는 발화자·메시지 ID·원문 근거를 붙여 `ExtractionBatch`로 검증한다. 현재 베이스/adapter 로딩과 생성 시 adapter 비활성 정책을 유지한다. 후보 생성 이후 자동 도구 실행·채점·일정 생성은 하지 않는다.

- 추출용 출력은 EOS로 완결되어야 한다. 형식 오류는 검증 오류 코드와 함께 1회만 재시도하며, 추론 오류는 반복 호출하지 않는다.
- 장소는 원문 이름과 Unicode/공백 정규화만 허용한다. 실제 장소 조회나 주소·좌표 확인은 별도다. 같은 이름을 여러 참가자가 말하면 근거를 합치고 지지는 각 작성자로 남긴다.
- 개인 예산/귀가 마감은 완전한 자기 조건 문장과 값을 검증한다. 명시적 숫자·오전/오후 변환의 규칙 보조는 `condition_rule_assisted`로 구분한다. 가정·타인 발언·모호한 복합 금액·미지원 조건은 hard 조건으로 추측하지 않는다.
- 과거 대화는 최대20개, 추가 토큰은 최대2000개로 제한하며 현재 메시지를 우선한다. 새 사실의 근거는 `recent_messages`만 허용한다.
- 구조 실패 메시지는 Backend `failed-extraction:<room_id>` 기록에 남는다. 새 메시지는 계속 처리하며 기존 수동 재계획 버튼으로 실패분을 재시도한다. `filtered`는 제안별 거절이고 `failed`는 배치 반영 실패다.

선택 의존성은 `requirements-local-qwen.txt`에 포함된다. 핵심 fake/fixture 경로에는 torch/LMFE가 필요하지 않다. Pydantic2.14.3/LMFE0.11.3, Transformers4.57.6/Torch2.14.1+cu126/PEFT0.21.3 조합에서 실제 검증했다.

전용 재생은 저장소 루트에서 실행한다. 공급자는 fixture이고 도구를 자동 호출하지 않는다.

```powershell
python -m ai.eval.extraction_replay --model-backend local_qwen --base-model-path C:/path/to/Qwen2.5-1.5B-Instruct --adapter-path submission/weights --compare-unconstrained --output .planning/extraction-report.json
```

32개 입력을 제한/자유 생성으로 각각 실행하고 입력별 결과, 근거·소유권 오류, 출력 토큰·재시도·지연을 기록한다. 정상 생성의 형식 성공과 내용 정확도를 구분하고, fake 결과를 실모델 품질로 집계하지 않는다. 자세한 범위와 결과는 `docs/verification/grounded-qwen-extraction.md`를 따른다. 실제 API·영업시간·가격 검증은 이 평가에 포함하지 않는다.
