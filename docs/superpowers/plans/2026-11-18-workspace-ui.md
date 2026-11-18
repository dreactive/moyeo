# Workspace UI Implementation Plan

> **For agentic workers:** Use subagent-driven-development / inline execution as assigned. User approved implementation and final integration into remote develop.

**Goal:** 별도 로그인·가입 → 방 생성/참가 → 첨부 화면의 여행 작업방을 구현한다.
**Architecture:** 바닐라 ES modules, same-origin HTTP/SSE, 서버 DTO를 유지한다. 세 작업자는 소유 파일을 분리하며 실행 로직 약 300자 내외의 작동 단위마다 검증하고 선택 stage/commit한다.
**Tech Stack:** HTML/CSS, Node 24 tests, 기존 FastAPI, Kakao adapter.
**Spec:** ../specs/2026-11-18-workspace-ui-design.md
**Base:** develop 2cddfbdf8400ec3377888c6bd12dca3f4cb5277f. Branch codex/workspace-ui, native isolated worktree.

## Global Constraints
- frontend/** 및 UI 설계·계획·검증 문서만 수정. 스키마 작업의 ai/**, backend/**, 공통 계약을 수정하지 않는다.
- 개인 AGENTS.md/.local 스킬은 stage하지 않는다. 과거 사용자 문서/수정은 보존한다.
- 약 300자는 실행 로직(테스트 포함)의 목표이며 기능 경계를 우선. HTML/CSS/문구/문서는 제한 제외. 한꺼번에 만든 코드를 나중에 기계적으로 쪼개지 않는다.
- API DTO·쿠키·SSE·target·소유권·가격 계산은 유지. fixture/live와 저장 공간을 분리한다.
- 사용자 승인: 새 브랜치, 구현, 작은 커밋, 충돌 없는 원격 develop push. 통합 전 fetch·전체 검증·리뷰. force push 없음.

## Review Focus
1. 로그인 401과 서버 503을 구별하고 이전 방이 있어도 로그인 후 방 선택.
2. fixture 다중 페이지 이동 시 모드·로그인·방 설정 유지, live와 격리.
3. 입력중 focus/IME/스크롤과 두 지도는 채팅 수신에 영향받지 않음.
4. review_plan 고정, target 전체 비교, 3/4 미확정, 공식 confirmed 수신 후 확정.
5. 비용 null/개인 소유 비용/늦은 응답과 날짜 선택에서 거짓 합계나 공동 변경 없음.

## Task A — 인증·방 진입 (agent entry_flow)
Files: login.html/signup.html/rooms.html; src/session.js/auth-page.js/rooms-page.js/trip-form.js/fixture-session.js; api.js/fixture-api.js; tests/entry*.test.js/fixture-session.test.js and scoped existing tests if necessary.
Interfaces: session.js exports pageUrl(path), navigate(path), readRoomId(), saveRoomId(id), clearRoomId(), requireSession(), signOut(), preparePage(). requireSession returns user|null and redirects only initial 401. preparePage sets mode banner and data-app-link hrefs. trip-form.js exports restoreTripForm(snapshot) returning baseline config, readTripForm(form) returning {title,...TripConfig}, bindFixedCostControls() (once per page). Existing trip-input.js/fixed-costs.js reused.
- [ ] Small loops: status-preserving API error → mode URLs/storage → fixture session persistence → auth flow → room creation/join and shared trip form.
- [ ] Each nontrivial behavior: failing focused test, observe failure, minimal implementation, passing focused test, reviewed selected diff and commit. UI-only markup verified via browser.
- [ ] Auth success always rooms; register gets cookie session; initial /me401 redirects, network503 stays with retry; no secrets stored.
- [ ] Fixture unauth first, explicit fake login, persist snapshot/scenario/user ID in fixture namespace across navigation; hydrate places from scenario.

## Task B — 静的 layout/style (agent layout)
Files ONLY: frontend/index.html, frontend/workspace.css.
Interfaces: include /styles.css then /workspace.css, meta Kakao key preserved, script /src/room.js. body.workspace-page. Header IDs session, room-heading, room-meta, members, invite-code, copy-invite, logout, open-settings. Status mode,error,retry. Main IDs agent,replan,messages,history,new-messages,message form textarea[name=text], constraints,questions,items,conflicts,route-days,route-summary,route-map,place-map,place,cost,plan,confirmed-plan. Keep fixture-controls/user/scenario/replay/reconnect. Keep existing trip form fields/add-cost/fixed-costs inside dialog#trip-settings; close button data-close-settings. Cards: conditions/route/place/cost; consensus bottom. Do not change JS.
- [ ] Commit markup as independently valid declarative unit preserving existing IDs.
- [ ] Commit scoped CSS as independently reviewable declarative unit. Cover .auth-page, .rooms-page for Task A.
- [ ] 869x1206 and 1440x900 proportions, gray/white/purple, message bubbles/cards, no body min-width1050. Narrow fallback. /dev unaffected.

## Task C — 메인 연결·표현 (root)
Files: room.js, chat.js, workspace-view.js, state.js, items.js, plan.js, cost.js, map.js/kakao-adapter.js/place.js; focused tests excluding task A files.
- [ ] Test-first small units: incremental chat/IME/scroll → header/banner/date state → per-user cost → confirmation summary → field-oriented conditions/questions → selected-day maps/place context.
- [ ] Refactor room bootstrap/bindings to Task A interfaces and Task B IDs, keep one SSE + cleanup and pending/failure status.
- [ ] Guard render regions against redundant replacement of focused forms/maps; no place requests on chat-only updates.
- [ ] Existing core tests remain green or adapt assertions to user-visible equivalent behavior; preserve domain assertions.

## Task D — 통합·리뷰·전달 (root + fresh reviewer)
- [ ] Run node --test frontend/tests/*.test.js; Backend full suite via existing Python environment; AI suite as integration regression if schema lands. Record environment limits explicitly.
- [ ] Browser verify all four pages, fixture persistence, live cookie create/join, two clients/SSE, chat and confirm scenarios, 869/1440/narrow layouts and /dev. Capture screenshots.
- [ ] Review complete feature diff independently, fix Important findings in small tested commits.
- [ ] Fetch origin/develop and inspect other schema/deploy commits, merge remote into feature branch without rewriting history, run integrated tests.
- [ ] Push HEAD:develop without force, verify remote SHA; update/create existing master<-develop PR according to personal workflow where tooling permits. Preserve branch/worktree.
