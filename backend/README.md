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

SQLite persists identities, opaque sessions, room snapshots, event history, run provenance, and immutable confirmed-plan history. Normalized provider observations and sanitized diagnostic traces are room-scoped process memory; provider raw responses are not stored in permanent trace logs. A server restart requires fresh observations for details. Keep one uvicorn worker for this MVP's in-process queue and observation store.

Independent tests exclude the integration marker. Explicit connected runtime tests use:

```powershell
backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q -m integration
```

See docs/verification/backend.md and docs/verification/integration.md for actual executed modes and limits. Fixture/fake results do not establish Qwen quality or live provider coverage.

Open SSE responses can keep uvicorn waiting indefinitely at shutdown without a grace limit. The documented commands set --timeout-graceful-shutdown 5 so remaining HTTP streams are cancelled and application lifespan cleanup can run. The separate actual-Qwen/open-SSE probe closed the runtime once with a two-second limit. An active GPU operation may still need to finish before the serialized model close acquires its lock; this is not a five-second inference cancellation guarantee.
