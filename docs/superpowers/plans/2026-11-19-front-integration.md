# Front Integration Implementation Plan

> **For agentic workers:** Apply test-driven-development and verification-before-completion; user explicitly requests one final commit, no300-character splits.

**Goal:** Adopt feat/front layout and room management on latest develop while preserving deployment, AI and state protections.
**Architecture:** Vanilla ES modules and FastAPI. Overlay frontend presentation, selectively port backend capabilities and retain develop integration boundaries.
**Tech Stack:** Node24 tooling, browser JavaScript/CSS/HTML, Python FastAPI/SQLite.
**Spec:** ../specs/2026-11-19-front-integration-design.md

## Global Constraints
- Preserve Vercel static build/API proxy and COOKIE_SECURE.
- Preserve AI extraction/context/quarantine/retry/empty-job suppression.
- Preserve drafts, focused decision forms, accumulated chat, pending guards,401/409 recovery and fixture isolation.
- Do not edit AGENTS.md or .local skill; do not commit local planning/data or credentials.
- One final commit only; non-force push to origin develop after verification.

## Review Focus
- Two members joining or deleting while agent work/events are active.
- Empty optional dates/budget and preexisting room data.
- Incoming updates while user edits or sends a message.
- Same origin Vercel aliases/auth cookies and API proxy after layout replacement.
- Participant changes invalidate confirmation and deletion cannot resurrect rooms.

### Task1: Backend room management
Files: backend/{auth,db,schemas}.py, routes/{auth,rooms,static,messages}.py, services/{rooms,agent_jobs,events}.py and app.py, relevant backend tests.
Interfaces: GET /api/rooms -> {rooms}; POST /api/rooms accepts empty initial config; POST /api/rooms/{id}/members {email}; DELETE owner-only; PATCH trip supports title and optional dates; room snapshot exposes owner_id.
- [x] Add failing behavior tests for list/create/invite/owner/delete/optional dates and secure cookies.
- [x] Selectively port feat/front logic, preserving current job/extraction and heartbeat behavior.
- [x] Run backend tests and AI contract regressions; record results.

### Task2: Frontend layout and state integration
Files: frontend HTML/styles, src modules and focused tests. Preserve scripts/,vercel.json,package.json build/engine and useful develop modules/tests.
Interfaces: new lobby + controller use Task1 API, shared snapshot/target contracts unchanged.
- [x] Adopt branch presentation/modules and new tests; retain existing regressions.
- [x] Preserve develop state/submit/session/recovery/route protections with failing regression cases first.
- [x] Run all frontend tests; resolve genuine layout assertions to new observable behavior.

### Task3: Deployment and route integration
Files: frontend/scripts/deployment.mjs, backend static aliases, deployment tests/docs.
- [x] Test /login,/signup,/rooms aliases and unchanged /api external rewrite with no-store.
- [x] Extend aliases in static build without removing existing routes or public key injection.
- [x] Build with test-only HTTPS origin; inspect static/config output and run full tests.

### Task4: End-to-end verification and delivery
- [x] Start isolated fixture server and verify signup/login/create/invite/join/main/logout via API and browser.
- [x] Review complete diff independently; fix material findings and rerun affected suites.
- [x] Record test/browser evidence in docs/verification/front-integration.md; exclude personal files and secrets.
- Delivery procedure: fetch develop again, stage reviewed files, create one commit, push non-force HEAD:develop and the feature branch, and update the existing master<-develop PR. Record the resulting commit and remote verification in that PR.

User coordination: the user confirmed develop is updated and approved the reported BE conflict resolution. Use e6f4965's new AI flow as the basis and preserve both the room lifecycle protections and every attached FE preservation item. Finish with one commit and non-force push after final checks.

### Task5: Approved upstream reconciliation
- [x] Preserve run_current/is_current, request/result pipeline and deletion-terminal worker behavior.
- [x] Combine room projection/lifecycle helpers, location_only/direct details, optional dates and trace guards.
- [x] Integrate request progress, versioned partial itinerary/costs, agreement, new question fields and coordinate-only maps into the new layout.
- [x] Preserve and run both upstream and local regressions, browser entry flow, build and independent review.
- [x] Resolve review findings with regressions: open-only question answers, current-draft menu lookup, running replan protection, focused-form reconciliation and removal of obsolete detail requests.
