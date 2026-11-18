# Candidate generation only — 2026-11-18

Branch: `codex/candidate-generation-only`, based on `develop` at `f583969`.

Planning runs prepare context, generate candidate actions, add grounded alternatives,
validate arguments/references, remove duplicates, and return the list in `candidates`.
They perform no candidate scoring, action selection, automatic tool calls, plan reuse,
or plan assembly. `plan_draft` stays null, new `observations` stay empty, and
`completion` stays `needs_input`. Candidate traces use `selected_index: null` and
`scores: []`. Extraction-only goals and existing early exits retain their behavior.
Explicit tool execution remains available. The submission package is preserved;
local Qwen still loads the supplied base/adapter and disables the adapter for generation.

Validation:

- AI suite: 114 passed (`pytest -c ai/pytest.ini ai/tests -q`).
- Backend default suite: 111 passed, 3 integration cases deselected; existing
  Starlette/httpx deprecation warning. Used the existing Backend integration venv.
- Fake/fixture replay: 18/18 passed. Expected results now cover candidate batches,
  zero automatic tool calls and no plan draft, rather than finished itinerary costs.
- Separate read-only code review found no actionable issues.
- CLI output is covered by the AI suite, including candidates without a trace sink.

Historical scoring-based live-model timings and full product integration reports
describe the previous implementation. They are not verification of this branch.
No live model/GPU or paid provider calls were made for this change.
