# Developer Swagger sandbox — 2026-11-18

Implemented on `develop` from `f583969`; the separate candidate-only branch was
not merged. Six developer-only POST operations are documented in Swagger:

- `/api/dev/tools/search_places`
- `/api/dev/tools/get_place_details`
- `/api/dev/tools/get_car_route`
- `/api/dev/tools/build_itinerary`
- `/api/dev/tools/calculate_costs`
- `/api/dev/agent/utterance`

## Verified behavior

- Login cookie and nonempty matching `X-Dev-Token` are required for every call.
  Swagger's Authorize control also covers the existing room trace operation.
- Typed editable requests and response envelopes are published in OpenAPI.
  All five serialized OpenAPI examples executed through the real fixture registry
  during independent review. Backend-owned examples do not import AI at boot.
- Place identity, fixture menu price (10,000 KRW), route units (4,000 m / 600 s),
  itinerary start time and costs are checked against actual code results.
- The synthetic cost example reports 120,000 KRW known total, two unknown lines
  and null full total. Explicit calculation arguments contradicting observed
  prices/route seconds are rejected. Unknown numeric text is 422, not a crash.
- Tool results include observations and reusable context. Calls never apply
  proposals, update room observations or enqueue room jobs. Supplying a real
  room ID in an utterance does not change its stored snapshot.
- Utterances preserve text/author and create fresh message/run IDs. Real fake-model
  extraction returns a 150,000 KRW proposal for the example utterance. Author IDs
  must belong to the supplied context. Results and sanitized trace are returned.
- Tool-only requests do not create a model. Developer-only lazy runtime creation
  runs in a worker thread and concurrent first calls share one app-owned lock.
  The existing application AI runtime is reused when configured. Shutdown closes
  a separately created developer runtime.
- Invalid server modes, missing live provider credentials, missing dependencies
  and invalid model paths produce safe 503 responses. Provider exceptions are
  502, including exceptions caught by the core Agent loop and reported in a
  termination trace. Model/validation exception terminations are also surfaced;
  ordinary needs-input decisions remain successful responses.

## Final verification

| Check | Result |
| --- | --- |
| Backend default suite with AI/Torch/Transformers imports blocked by a fresh-process finder | 128 passed, 23 deselected |
| Backend explicit integration suite, fake/fixture | 23 passed |
| AI offline suite (`not live_model and not live_provider`) | 113 passed |
| Independent read-only code review | Five P2 findings addressed with regression tests; no remaining/deferred findings |
| Diff whitespace checks | Passed |

The Backend runs retain the existing Starlette/httpx deprecation warning.
Actual live-provider HTTP failures are simulated in the new tests; no paid
provider call, actual Qwen inference or GPU performance measurement was performed
for this change. Historical product/live evidence is documented separately.

## Review fixes

1. Validate server mode allowlists and credentials, and classify missing model
   files as runtime configuration failures.
2. Translate caught exception terminations to HTTP failures at the developer
   boundary while preserving the core Agent loop.
3. Catch decimal conversion failures as invalid input.
4. Offload and serialize the developer's first runtime creation.
5. Mark actual AI-dependent tests as integration so Backend-only tests remain
   independent. A fresh-process blocked-import suite confirms that boundary.

The implementation follows the local small-commit workflow. The runtime-creation
fix keeps its lock, thread handoff and concurrency regression in one working
commit because splitting them would leave the safety property unverified.
