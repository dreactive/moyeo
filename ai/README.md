# Travel agent: auxiliary facts and supplied Qwen judge

The external auxiliary model structures user facts with source quotes. Service code builds valid actions, the supplied Qwen + LoRA scores the actual candidates, and RegisteredTools executes the selected arguments. Backend owns IDs, confirmations, state versions and DB writes.

## Setup

Use Python 3.12 from the repository root:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r ai/requirements-local-qwen.txt -r backend/requirements.txt
```

Copy `.env.example` to `.env`. Use `OPENAI_API_KEY`, not `OPEN_AI_API_KEY`; leave it empty until a key is available. The recommended helper is `AUX_MODEL=gpt-6-luna` with `AUX_REASONING_EFFORT=none`. Model availability depends on the API account. See [model capabilities](https://developers.openai.com/api/docs/models/gpt-6-luna) and [API key setup](https://developers.openai.com/api/docs/quickstart).

Set local base/adapter paths, `MODEL_BACKEND=local_qwen`, `AGENT_MODE=local_ai`, `AUXILIARY_BACKEND=external`, `PROVIDER_MODE=live`, and the intended `BACKEND_DB`. Loading uses existing local files only. CUDA uses the supplied submission's bfloat16 policy; the adapter remains active for judging. Original submission files and weights are unchanged.

An empty auxiliary key produces an explicit extraction-failure receipt; it does not silently switch to fixtures. Standalone obvious greetings can skip both models. Existing manual tools do not need an auxiliary key.

## Decision path

1. The helper receives the current message batch and small room state. LangChain `with_structured_output(..., method='json_schema', strict=True)` validates its schema. The helper has no service tools.
2. If a current request needs prior context, code retrieves up to eight relevant original messages, within 12,000 characters, and makes at most one context-completion call. Historical messages cannot become new user evidence.
3. Code validates authors, current evidence quotes, values, target-specific opinions, corrections and negation. Unverified proposals are rejected. Hard conditions remain owner-confirmation proposals.
4. Code prepares complete canonical tool arguments independently for each available action. Valid branch: up to three distinct real tool calls plus an applicable cannot-answer response. Invalid branch: up to two real questions, an applicable cannot-answer and a grounded direct response.
5. Only actual candidates are used: zero means hold without judging; one is explicitly traced; two to four are supported. Extra tool work remains pending and appears as deferred candidates. No fake candidates or null required arguments are added.
6. Qwen scores with unchanged `submission.judge.judge_scores`: raw yes-minus-no logits, one forward per candidate. Highest score wins. No fallback to candidate zero, generation, or probability thresholds. Nonfinite scores and oversized inputs hold safely.
7. The exact scored tool name and arguments are validated and executed through RegisteredTools. New observations may enable another dependent round, with a fresh judge batch; a run is bounded to six rounds. This is one Qwen decision per round, not one forward for the entire run.

The internal action names are `tool`, `ask`, `unsupported`, `direct`, corresponding to `tool_call`, `request_for_info`, `cannot_answer`, `direct`. A tool being available does not mean the entire trip is complete. Unknown prices, quantities, anchors or unconfirmed hard constraints still block a ready plan.

Existing open questions are retained. A selected question adds only the selected new question; direct/cannot-answer responses execute no tool. Old context is reference material, not proxy support from its author.

## Backend and traces

```python
from ai.runtime import create_runtime
runtime = create_runtime(config)
result = await runtime.run(task, emit_trace, is_current=current_snapshot_check)
await runtime.aclose()
```

Create one runtime per application lifespan. A worker serializes model use and shutdown. Each run has an isolated context. Backend checks a substantive room-and-observation snapshot before execution and atomically before applying results, including new messages that do not bump versions. Stale runs are requeued without applying obsolete results.

Decision traces show candidate count, concrete arguments, source IDs, raw scores, selected index, decision context, timing and selection origin. Tool results identify `http`, `cache`, `local_calculation` or `fixture`. The existing developer trace page displays these events. Keys and private model reasoning are not included. Tracing can be disabled without discarding product observations.

The old `ai.runner` generation-preview functions remain available for historical extraction tests; production `AgentRuntime.run` uses `ai.judged_runner` and never calls Qwen generation.

## Verification

```powershell
python -m pytest -c ai/pytest.ini ai/tests -q -m 'not live_model and not live_provider'
# Run Backend separately with an isolated test env/DB; do not point tests at a real room DB.
python -m pytest -c backend/pytest.ini backend/tests -q -m 'not live_model and not live_provider'
cd frontend
npm test
```

Fake model + fixture auxiliary/provider modes are explicit offline evidence, not real model quality evidence. The local audit below uses scripted, explicitly labelled auxiliary facts, the actual supplied Qwen/LoRA, and the real registered provider. It also deliberately submits an ungrounded budget for rejection. It writes an isolated report and never opens a product DB for writing:

```powershell
python -m ai.eval.verify_judge_execution --base-model PATH_TO_BASE --adapter PATH_TO_ADAPTER_DIRECTORY --env-file .env --provider live --database PATH_TO_EXISTING_DB --output .planning/qwen-tool-execution/live-qwen-audit.json
```

The external auxiliary cannot be validated live until `OPENAI_API_KEY` is populated. Its actual LangChain request serialization and error handling are tested with MockTransport. See `docs/verification/2026-11-18-qwen-judge-tool-execution.md` for measured results and limits.

## Existing tool rules

Kakao Local/Mobility supply place and route observations; Apify supplies matched place details. A same-branch match requires provider ID or address and coordinates. Prices/hours remain unknown without evidence. `departure_at=None` means a current route and is never replaced with an invented future timestamp. Costs and itineraries use the existing canonical code inputs. Reservations and purchases are unsupported.

## Referenced detail requests

A current request such as “아까 내가 고른 두 곳 상세 정보 보여줘” uses grounded domain requests rather than new votes. The helper returns names and current/historical evidence; code resolves unique same-room PlaceRefs and exclusions. Scoped details calls suppress unrelated planning calls. The runner records completed/pending targets, persists them in the existing room JSON, and resumes saved targets without another auxiliary API call when no new message is present. Fresh user work owns its round; explicit same-owner corrections supersede conflicting saved scopes.

The user's portable semantic fixture is in `docs/verification/fixtures/auxiliary-qwen-two-places.json`. Run `python -m ai.eval.verify_context_requests` with local weight paths and an output path for actual Qwen judging plus the existing fixture executor. This case makes no external auxiliary or provider HTTP call. The separate live search audit verifies Kakao HTTP.
