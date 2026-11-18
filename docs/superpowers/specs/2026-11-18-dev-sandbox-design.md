# Developer Swagger sandbox

The developer needs editable inputs for the five registered AI tools and a way to
send an utterance directly to the Agent. Add six POST operations to Swagger under
`/api/dev`, without changing the ordinary user interface or persisting test calls.

## Approach

Use the existing FastAPI application, login cookie and `X-Dev-Token`. Each tool
has its own typed request schema and operation, rather than a generic tool-name
dispatcher or a separate server. Standalone, caller-supplied context makes tests
reproducible without creating a real room. No database room is loaded by these
operations. Developer authentication is shared with the existing trace route.

- `/api/dev/tools/search_places`
- `/api/dev/tools/get_place_details`
- `/api/dev/tools/get_car_route`
- `/api/dev/tools/build_itinerary`
- `/api/dev/tools/calculate_costs`
- `/api/dev/agent/utterance`

The five tool operations use the existing registry and its argument validation.
They return the result, a reusable observation and context including that
observation. Calculation arguments may be omitted to derive canonical arguments
from context; explicit arguments remain validated against context.

The utterance operation accepts text, an author belonging to the supplied
context, a goal and context. It creates an isolated run/message and returns the
actual Agent result plus sanitized trace events. It reuses the application's
local AI runtime when available, or lazily starts a developer bridge using the
same configured model/provider. Close that bridge during application shutdown.
Tool-only calls must not load a language model.

## Constraints and verification

Missing login is 401; missing, wrong or unconfigured developer token is 403.
Swagger exposes an API-key Authorize control. Invalid inputs are 422, upstream
HTTP failures 502, unavailable AI dependencies/runtime 503, without secret-bearing
exception details. Examples use a Backend-owned synthetic fixture and are runnable
with fake/fixture. Live calls explicitly use server-side provider configuration;
no fallback claims live success. No new dependencies. Backend still boots without
the AI package. No test call changes room messages, plans, observations or jobs.

Work on the requested `develop` branch in place, preserving the pre-existing
untracked extraction design/plan. Keep the candidate-only branch separate; this
feature does not change the current develop Agent loop. Verify HTTP schemas,
authentication, every tool against real fixture implementations, utterance identity
and isolation, errors, runtime closure and the existing Backend/AI suites.
