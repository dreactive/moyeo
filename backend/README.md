# Backend

FastAPI + SQLite, JSON-only AgentPort. Run commands from the repository root.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q
backend/.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

Use an actual installed Python executable if the Windows Store alias cannot start. This session used C:/Users/user/anaconda3/python.exe to create the isolated environment. In the managed sandbox, asyncio/TestClient and DNS needed the approved execution environment; this is an environment limitation, not a product assertion.

Open http://127.0.0.1:8000/ for the same-origin frontend when frontend/ exists. API routes also run without frontend/. Copy backend/.env.example to a local ignored .env or set shell environment variables. TRIP_ENV_FILE selects an explicit .env path; shell variables override file values. DEV_TOKEN must be nonempty for /api/dev/rooms/{room_id}/traces. Read your local .env to obtain the token; no token is embedded in the UI. /dev requires the same logged-in room member cookie plus X-Dev-Token.

Default AGENT_MODE=fixture does not import AI, torch, model packages, or provider SDKs. FixtureAgentPort returns the frozen sample result for its explicitly seeded item-a/item-b scenario. Unseeded rooms return needs_input with fixture observations. It does not understand arbitrary Korean. backend/adapters/fixture_result.json is copied from docs/contracts/examples/agent-result.example.json v0.2 and remains marked fixture. It is not live data.

For the AI runtime, install ai/requirements.txt into the chosen integration environment, set AGENT_MODE=local_ai, MODEL_BACKEND=fake and PROVIDER_MODE=fixture. The bridge imports ai.runtime only during application lifespan and creates one runtime. Failures remain failures and are never replaced with a successful fixture run. For actual Qwen/live, follow ai/README.md and supply BASE_MODEL_PATH, ADAPTER_PATH and TRIP_ENV_FILE. Only one session should own GPU execution.

KAKAO_JAVASCRIPT_KEY is a public browser key. Only that key is inserted into the index meta tag at runtime; REST, Mobility, Apify, and developer tokens stay server-side. Register the actual origin in the Kakao app's JavaScript SDK domain settings. The static frontend is served after /api routes. No CORS proxy or separate frontend build is needed.

SQLite persists identities, opaque sessions, room snapshots, event history, run provenance, immutable confirmed-plan history, and the two-stage agent jobs. Real LocalAIBridge processing uses one auxiliary extraction worker and one guarded Qwen/tool worker; completed raw structured interpretations are re-grounded against current room state. Bounded queues use SQLite as backlog and separate extraction/execution cursors. Completed normalized read-tool checkpoints can be reused after restart only through the existing suitability checks; interrupted external reads can be retried, so external exactly-once calls are not guaranteed. Sanitized diagnostic traces remain room-scoped process memory. Keep one uvicorn worker; multiple independent server workers sharing these queues are unsupported. Run-only fixture ports retain their serial compatibility path. See docs/contracts/travel-api.md section 9 for phase, retry and persistence details.

Independent tests exclude the integration marker. Explicit connected runtime tests use:

```powershell
backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q -m integration
```

See docs/verification/backend.md and docs/verification/integration.md for actual executed modes and limits. Fixture/fake results do not establish Qwen quality or live provider coverage.

## Developer Swagger sandbox

Open [Swagger UI](http://127.0.0.1:8000/docs), log in through
`POST /api/auth/login` (or register a local development account), then select
**Authorize → DeveloperToken** and enter the server's `DEV_TOKEN` value.
All sandbox operations require both the login cookie and a nonempty matching
developer token. They are under **Developer sandbox**, with editable request
examples and response schemas. They do not require creating or joining a room.

| POST operation | Editable input | Inspect in response |
| --- | --- | --- |
| `/api/dev/tools/search_places` | `arguments.query`, `region`, `category` | `result.places`: IDs, names, addresses and coordinates |
| `/api/dev/tools/get_place_details` | `arguments.place_ref`, using an observed place ID | `result.menus`, `opening_hours`, `evidence` |
| `/api/dev/tools/get_car_route` | `arguments.from_ref`, `to_ref`, `departure_at` | `result.distance_m`, `duration_seconds`, `toll_krw`, `polyline` |
| `/api/dev/tools/build_itinerary` | Visits in `context.current_plan.days`, anchors in `context.config`, route observations | `result.days`, `questions`, `conflicts` |
| `/api/dev/tools/calculate_costs` | `context.config.fixed_costs`, observed menus, selected quantities, members and budgets | `result.total_krw`, `per_person_krw`, paid/planned balances and unknown count |
| `/api/dev/agent/utterance` | `text`, `author_id`, `goal`, `context` | `result` and sanitized `trace` |

For an offline first run, install `ai/requirements.txt` in the Backend environment
and use `MODEL_BACKEND=fake`, `PROVIDER_MODE=fixture`. The sandbox works even when
the ordinary Backend uses `AGENT_MODE=fixture`: tool calls use the actual AI tool
registry, and utterances lazily create a fake AI runtime instead of returning the
Backend's frozen response. Tool-only calls do not load a language model. If
`AGENT_MODE=local_ai` is configured, utterances reuse its existing runtime.

Select a request example, press **Try it out**, edit its JSON and press **Execute**.
The examples in `backend/dev_sandbox_fixture.json` are synthetic, including the
fixed November 21–22, 2026 dates. They include route observations so calculations
can run immediately. The cost example deliberately leaves fuel/parking and park
admission unknown: known total is 120,000 KRW, full total is null.

Each tool response includes `arguments`, `result`, `observation`, `provider_mode`
and a new `context`. To chain tools, copy the returned **context** into the next
request and use the returned place IDs. A request never updates server-side room
observations. For itinerary/cost operations, omit `arguments` or set it to null
to derive canonical inputs. You may also copy returned arguments into a request;
their prices, IDs and travel times must agree with context. To test a changed
cost, edit the corresponding fixed cost or observed menu in context first. To
test another visit time, edit the plan and provide route observations for its
actual departure time; missing prerequisites return 422 rather than invented data.

Utterance `author_id` must match a member's `user_id` in the supplied context.
`goal=extract` tests condition/place/support extraction, `new_message` follows the
ordinary message trigger, and `manual_replan` requests planning. Every call gets a
fresh run/message ID. On `develop`, planning uses the existing selection/tool loop;
the separate candidate-only branch has different planning behavior. Trace events
show the actual calls and decisions. The sandbox returns traces directly even if
room trace storage is disabled; nothing is written to `/dev` or room history.
Results/proposals are returned without being applied to room state.

To test actual data, use the server's `PROVIDER_MODE=live` and configured provider
keys. Replace synthetic references/observations with live search/details/routes;
fixture references cannot be used as live IDs. Use future, timezone-aware trip
departure times. Live provider calls may incur charges. For real model behavior,
use `MODEL_BACKEND=local_qwen` with the paths/dependencies in `ai/README.md`; fake
results do not establish Qwen quality. Responses distinguish 422 invalid inputs,
502 provider failures and 503 unavailable dependencies/runtime without returning
secret-bearing exception details.

Sandbox regressions requiring the real AI package carry the `integration` marker;
default Backend tests remain AI-independent. Run the explicit integration command
above after installing `ai/requirements.txt`. See
`docs/verification/dev-sandbox.md` for the executed modes, review fixes and limits.

Open SSE responses can keep uvicorn waiting indefinitely at shutdown without a grace limit. The documented commands set --timeout-graceful-shutdown 5 so remaining HTTP streams are cancelled and application lifespan cleanup can run. The separate actual-Qwen/open-SSE probe closed the runtime once with a two-second limit. An active GPU operation may still need to finish before the serialized model close acquires its lock; this is not a five-second inference cancellation guarantee.
