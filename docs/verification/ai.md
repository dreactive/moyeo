# S3 AI verification — 2026-11-18

Plan: docs/superpowers/plans/2026-11-18-ai.md, baseline 20db9c1.
Owner paths: ai/** and this document. Push/PR/integration belong to S2.

## Workspace and rulings

- Workspace: C:/Users/user/.codex/visualizations/2026/11/17/01a1ea46-36e4-7542-b516-bcd5bda0f153/trip-s3-ai
- Branch: work/ai.
- Native create_worktree failed twice with “Could not find a Git repository at sourceRoot” (Windows and slash spelling). Git rev-parse confirmed repository and baseline. Manual creation needed escalation for the source Git metadata; succeeded once. Native attach then returned “checkout exists but is not a managed worktree”. Coordinator authorized reusing this exact worktree. No product writes in source checkout.
- Ruling: use this isolated Git worktree explicitly for every shell command; native metadata detection is stale. Cost if wrong: desktop attachments absent, but Git isolation remains observable.
- Environment: Windows python alias inaccessible. Dedicated ai/.venv created from the bundled Python 3.12.14; system site packages inherited for existing local model packages. Core requirements separately pinned. Initial sandbox pip DNS failed; escalated installation succeeded.
- Ruling: keep execution ledger here inside owned paths instead of writing shared .superpowers files. A0→A4 runtime interface matches; A1→A2 PlaceDetails observations restore per-room references; A2→A4 arithmetic stays in tools; A3→A4 validated extraction only.

## Progress

- Support target linking for S2: ambiguous support questions use id `question:support_target:<source_message_id>`, owner_id=that message's author, target_ref=null. No support is created until the original author identifies the target. S2 can recover the original message ID from this prefix without adding contract fields; AI emits no proxy support or official confirmations.
- Small-commit boundary note: approximately 300 executable characters is the target. Complete JSON result schemas, one loop or one semantic validation plus its focused test sometimes exceed it slightly; these are retained as runnable natural behavior boundaries, never a completed large feature split retroactively.
- Async environment ruling: minimal asyncio.sleep(0) hangs in default Windows sandbox and succeeds with require_escalated (0.5s). Async tests/CLI therefore run escalated; application code does not bypass asyncio.

- A0: in progress. No live success claimed.
