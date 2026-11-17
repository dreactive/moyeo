# S1 frontend verification — v0.2

Workspace: C:/Users/user/.codex/visualizations/2026/11/17/01a1ea45-e5e7-72b1-bd85-e12da6b4cabe/trip-s1-fe
Branch: work/fe. Base: 20db9c11b2f8a6bdbfa1824720ca9aa502fe71a3.
소유 범위: frontend/**, docs/verification/frontend.md. 공통 계약 v0.2 변경 없음.
F1-F5 FE 구현 및 fixture 경계 검증 완료. 실제 인증/SSE/API/SDK/Qwen/4인 분리 로그인 완료를 의미하지 않는다.

## 실행 결정과 범위

- native create_worktree는 Windows/slash sourceRoot 모두 "Could not find a Git repository at sourceRoot ... on this host."로 실패했다. 셸에서 clean develop/origin을 확인하고 한 번의 수동 fallback으로 위 격리 worktree를 생성했다. 부모가 Git worktree list로 재사용을 확인했다. 원본 제품 파일은 수정하지 않았다.
- Python launcher는 실행 불가였다. 의존성 없는 Node 정적 서버(127.0.0.1:5173)로 대체했다.
- 초기 sandbox 서버는 다른 세션에서 접근하지 못했다. require_escalated로 서버를 재실행했고 HTTP200을 확인했다. 서버는 frontend/server.js만 제공하며 API는 404다.
- 실행 ledger는 소유권을 지키기 위해 이 파일에 둔다. 별도 루트 scratch/설정 파일은 추가하지 않았다.
- F1 state/API → F2 events/F3 plan → F4 지도/경비는 같은 snapshot/다섯 target 필드를 공유한다. F5 trace는 일반 SSE와 분리한다.
- 입력/고정비/SDK helper는 frontend 내부의 순수 모듈로 분리했다. 계약 endpoint와 DTO는 변경하지 않았다.
- 작은 작동 단위별 검증·커밋을 반복했다. 초기 transport/연결 단위 일부는 약300자 로직 목표를 넘었으며 자연스러운 HTTP/초기화 경계를 유지했다. 이력을 다시 나누거나 재작성하지 않았다.
- fixture는 사전 기록 DTO를 재생하고 원시 입력을 echo한다. 실제 한국어 이해·지지 판정·재계획·보안 알고리즘을 구현하지 않는다.
- unmatched confirmed 항목은 ‘새 안 · 미확정’으로 중립 표시한다. Backend 소유인 지지 판정을 FE에서 다시 계산하지 않는다.

## 기능과 증거

| 범위 | 결과 | 근거 |
|---|---|---|
| F1 / C41-C43 | fixture/live transport, 초기화, 화면 구획, 개인 상태 경계 구현 | api/state tests, HTTP smoke, 부모 초기 화면 관측 |
| F2 / C06-C08,C12 | 계정/입장/생성/PATCH, 거점/고정비 UUID, 대화/근거/단일 이벤트 연결 구현 | api/events/state/trip-input tests, fixture echo, 부모 사람/Agent 분리 관측 |
| F3 / C10,C13-C24,C45 | 서버 색상·소유 조건·질문·충돌, 5필드 target, 검토/초안/과거 스냅샷 구분 | plan/items/fixture/display tests, 부모 3/4/4/4와 새 초안 관측 |
| F4 / C25-C33,C46 | 독립 지도 adapter, 개인 상세, 메뉴/시간/출처/null/예산 구분 | display/kakao tests. SDK 테스트는 대역이며 live 성공 아님 |
| F5 / RF5 | 별도 /dev, token 헤더 전용/입력 비움, 네 trace event/점수/도구/반영 렌더링 | trace tests. fixture 거부는 실제 접근제한 보안 성공 아님 |

검증 모드는 모두 fixture/fake 또는 Node 경계 검사다. 기준 run_id: run-fixture, run-fixture-ready, run-fixture-answer, run-fixture-selected. plan_revision 1/2는 명시적 기록이며 실제 Backend 해시 생성 성공을 뜻하지 않는다.

## 검증 명령 / 실제 결과

- Node v24.22.1.
- workdir 위 workspace에서 node --test frontend/tests/*.test.js: **23 tests, 23 pass, 0 fail** (최종 기록 시).
- frontend 작업 디렉터리에서 node --test tests/*.test.js: 23/23 pass. npm.cmd는 환경에 없어 실행 실패했다. package.json scripts는 선택 사항이며 의존성 설치는 필요 없다.
- frontend/src/*.js 및 frontend/server.js 전체 node --check: exit 0.
- 정적 HTTP smoke: /, /dev, styles.css, 모든 src/*.js, fixtures/*.json 및 /api/auth/me 총 **25 경로 통과**. 정적 자산200, JS MIME text/javascript, API404.
- live request 실패503 전파 / explicit mode=fixture만 fixture 선택: api.test.js.
- POST/SSE 중복 메시지 1개, 중복도 room seq 진행, 오래된 refresh/action 응답 거부, 닫힌/다른 방 구독 미수신: state/events tests.
- 모든 21개 기록 시나리오의 전체 공동 렌더러, review/active_target 동일성: display.test.js.
- 3/4 미확정 → 같은 target 4/4, revision2 확인 보존, stale target 거부, 본인 철회가 타인 표를 지우지 않음: fixture.test.js.
- 새 초안에 없어도 검토안에 있는 개인 장소 유지, 개인 지도 변경이 전체 adapter를 바꾸지 않음: state/display tests.
- 총액null/시가/메뉴미등록/공유단위/공급자기준일null, 예산 allowance120000/계획후50000: display.test.js.
- header-only X-Dev-Token, URL에 token 없음, fixture403/정상조회/run filter, 네 event 연결: trace.test.js.
- 선택 장소·동선·경비는 같은 표시 plan 기준. 개인 조회는 GET이며 공동 mutation을 부르지 않는다.

초기 실패를 보고 고친 회귀: 미구현 상태 구독/target 비교/anchor 검증, review 선택 해제, 다른 방 action 응답, 과거 confirmed의 잘못된 노랑, market fixture 메뉴 누락, 시나리오 간 장소 데이터 누출, room seq 누락, fixture 철회가 다른 표를 지움. 최종 suite에 실패 없음.

## 별도 부모 UI 증거

부모 세션이 require_escalated HTTP200 뒤 새 IAB 탭에서 관측했다고 전달한 결과:
- 초기 A 빨강1/3, B 노랑3/3, 사람 채팅 왼쪽/Agent 오른쪽 분리.
- 시나리오 03 4/4: 두 항목 초록 확정 및 confirmed_plan revision1.
- 시나리오 04: review revision1/3표 유지, 새 안 전환 버튼.
- A장소 선택 → 재연결 재생 후 상세 유지.

이는 부모의 fixture UI 관측으로 기록한다. 이 S1 세션의 CUA는 iab 미제공 후 native Chrome URL 판별 실패로 중단됐다. 본인 브라우저 관측으로 바꾸어 기록하지 않는다. 최종 trace 화면과 모든 폼의 실제 브라우저 입력은 별도 미검증이다.

## 외부 리뷰 반영

부모의 읽기 전용 리뷰 3건은 재현 테스트 실패→수정→suite 통과:
1. roomAction이 방 이동 후 늦은 응답을 적용함 → 캡처한 room_id와 현재 snapshot.seq를 공통 guard로 비교.
2. 과거 confirmed를 무조건 supported로 바꿈 → 같은 표시 target/item_version이 아니면 중립 미확정. FE 다수결 재계산 없음.
3. 개인 선택 유지가 current_plan만 봄 → 표시하는 review_plan 우선으로 검사.
후속 부모 리뷰는 HTTP payload·trace token·위 세 경계에 추가 결함 없음을 전달했다.

## G3/G4 미검증·통합 요청

- 실제 Backend cookie 가입/로그인/로그아웃, 서로 분리된 4인 로그인, 권한 거부, 실제 SSE 전송/네트워크 재연결.
- 모든 TripConfig/CostLine 입력·질문·대안·확인·철회가 Backend에 저장되고 실제 재계획되는지. fixture echo를 해당 성공으로 세지 않음.
- 실제 지도 키/허용 도메인/Kakao SDK, 여수 실API 경로/메뉴/가격/시간/유류·주차 데이터.
- 실제 Qwen run_id/점수/정규화 결과와 개발자 trace 대조. fixture trace의 model_mode는 fake.
- 최종 /dev 접근제한 실제 보안 검증과 브라우저 폼/trace 전체 수동 점검.
- 최종 develop push/master PR은 S2만 수행. S1은 push/PR을 실행하지 않았다.

## 커밋 인계

아래 목록 + 이 보고서 마감 커밋까지가 인계 범위다. 기준 20db9c1..work/fe를 순서대로 통합한다. 최신 HEAD는 최종 응답 또는 git rev-parse work/fe로 확인한다.

0d7c0f3 feat(fe): scaffold contract fixture workspace and travel layout
5199ef0 feat(fe): serve standalone fixture assets on port 5173
a090b6f feat(fe): isolate personal selection from room snapshots
e32a8e0 feat(fe): publish snapshot updates with removable subscribers
1031485 feat(fe): keep explicit fixture and same-origin live requests separate
46e6b03 feat(fe): route fixture identity and room place lookups
5cafe49 feat(fe): render room participants and separate agent status
24a4a6c feat(fe): bootstrap explicit fixture room with persistent mode label
ca1a083 feat(fe): pin displayed review to its complete confirmation target
66130f7 feat(fe): show immutable review and historical plan content
a1321e1 feat(fe): display server decision colors and independent conflict markers
47cc248 feat(fe): show owner-only conditions and blocking alternatives
be7b5d2 feat(fe): render field-specific questions with explicit server targets
c943398 feat(fe): distinguish paid budget allowance from planned balance
0b5ff6a feat(fe): preserve market prices missing menus and evidence timestamps
0c632cb feat(fe): render independent route and personal coordinate adapters
0c8ca81 feat(fe): scope fixture event subscriptions to the current room
0df9fcf feat(fe): keep one room SSE and refresh after reconnection
f57fadd feat(fe): deduplicate saved human messages across POST and SSE
bdb42d5 feat(fe): enter rooms with one subscription and ignore stale snapshots
afa9c29 feat(fe): render chat and shared plan from one room snapshot
807be57 feat(fe): submit cookie-based account and invitation forms
7d87de8 feat(fe): send human messages and close room events on logout
70ae741 test(fe): record fixture review conflict budget and question scenarios
6a3f5eb feat(fe): replay recorded scenarios with explicit fixture user controls
2095a53 feat(fe): simulate saved message responses and duplicate delivery
f48f0d7 feat(fe): send displayed target for plan confirmation and withdrawal
80e3fc9 feat(fe): submit typed question values and owner decision actions
faa7c1e feat(fe): replay recorded confirmation and alternative responses
0455128 feat(fe): preserve missing anchors and reject partial coordinates
69e7a64 feat(fe): edit fixed costs with stable browser-generated IDs
f43b1e3 feat(fe): submit trip anchors and raw fixed cost inputs
1982639 feat(fe): restore trip inputs and fetch historical source messages
5758704 feat(fe): load route places and keep personal detail selection local
fdb1a8f fix(fe): retain personal place selection from the displayed review
69be455 fix(fe): reject stale action responses after room navigation
ff9be78 fix(fe): show unmatched confirmed items as unconfirmed without invented votes
7516f85 feat(fe): echo fixture room and trip inputs without mutating history
bd2da2a feat(fe): echo fixture questions and owner constraint responses
d94b144 feat(fe): retain question target mappings in fixture input echoes
47c17da feat(fe): isolate developer trace access with header-only token
fe2918a feat(fe): render linked trace events and explicit fixture access responses
95b8932 test(fe): verify developer header boundary and fixture denial
5a0f0a7 test(fe): include comparative decision scores and applied-state trace
f3bc6bb feat(fe): load optional Kakao public JavaScript SDK
166457d feat(fe): draw independent SDK map instances and bounded markers
d6a9e50 feat(fe): connect optional SDK adapters to server routes and local selection
c9e34be test(fe): record separate confirmation targets for activated drafts
f5afc3a fix(fe): validate fixture target before replaying confirmation
88a56f5 fix(fe): reset place variants between fixture replays
eb7c153 fix(fe): preserve market menu fixture separately from missing menus
fd20cac feat(fe): expose live connection retry without fixture fallback
390aba6 test(fe): cover immutable history and question ownership in fixture echoes
365c810 fix(fe): preserve room sequence when applying SSE messages
78a642a fix(fe): advance event sequence even for duplicate message deliveries
31ef09e test(fe): replay fixture decisions through whole-plan confirmation
c4bac34 test(fe): render every recorded scenario against frozen target invariants
d9268e0 fix(fe): align personal question fixture with constraint ownership
d6645b0 fix(fe): clear stale trace output before a new authenticated lookup
61bd519 test(fe): verify linked decision tool and state trace rendering
83476b9 test(fe): validate optional SDK adapter inputs without claiming live maps
f0f167a refactor(fe): organize module imports and normalize final file endings
786d8f6 fix(fe): keep other confirmations when fixture user withdraws

38ab4c0 docs(fe): record F1-F5 verification evidence and integration handoff
마감 결정: 사용자가 S2 통합을 지정했으므로 work/fe와 worktree를 그대로 보존한다. S1 push/PR/merge 없음.

## F4 후속 리뷰 — 상세 응답 경합 (2026-11-18)

P2 재현: 같은 방/장소의 GET 두 개를 fake Promise로 제어했다. 새 요청이 22,222원으로 먼저 완료되고 옛 요청이 11,111원으로 나중에 완료되면 이전 구현이 옛 가격/근거를 표시하는 실패를 관측했다.

- 9d207a7: 증가하는 상세 요청 sequence를 캡처하고 최신 요청만 렌더링한다.
- 9aac375: 표시 중인 review_plan 우선 confirmation_target을 값으로 복사한다. 응답 시 다섯 필드(참가자/조건/근거/plan version 및 content_hash)가 바뀌면 폐기한다. 새 요청이 아직 시작되지 않은 경우도 보호한다.
- 51c3778: 새 초안만 바뀌고 검토 target이 유지되면 정상 응답이 수락됨을 검증한다.
- 추가 재현: revision1 GET 대기 → revision2/evidence2 snapshot → 같은 장소 새 GET 먼저 완료 → 옛 GET 완료. 22,222원/price-22222가 유지되고 price-11111은 표시되지 않는다.

변경 범위: frontend/src/place.js, frontend/tests/place.test.js, 이 검증 기록만. HTTP/DTO 변경 없음. Node 제어 응답 테스트이며 실제 API/SDK 관측 증거로 바꾸지 않는다.
최종 검증: node --test frontend/tests/*.test.js **27/27 pass**, node --check frontend/src/place.js 통과, staged diff/변경 경로 검토. 기존 23개 테스트도 모두 통과했다.
통합 추가 범위: 기존 인계 6f11ccd 다음의 커밋만 순서대로 가져온다. work/fe는 보존, push/PR/merge는 S2 소유다.

## 최종 FE 리뷰 후속 — 폼 병합·첫 SSE·확정 색상 (2026-11-18)

- 3234017: 첫 EventSource onopen도 기존 onReconnect 복구 콜백을 실행한다. initial GET와 SSE 설립 사이의 갱신 간극을 snapshot 재조회로 복구한다. 이후 재연결도 동일하게 조회하고, 닫힌 연결은 콜백을 실행하지 않는다. 초기 복구 횟수 0≠1 실패를 관측한 뒤 통과했다.
- ec5fdb1 / 2dbab2c: 입장 시 폼을 같은 직렬화 함수로 읽어 편집 기준을 보관한다. 저장은 기준과 다른 필드만 PATCH한다. 예산200000 입장 → 최신 snapshot 예산300000 → 종료시각19:00 편집의 PATCH는 day_end_time만 포함한다. 편집 중인 DOM 입력을 SSE/저장 응답으로 복원하지 않는다. 성공 후 제출값으로 기준만 갱신하며, 다른 방 입장으로 기준이 바뀐 경우 옛 응답이 기준을 교체하지 않는다. 변경 없는 저장은 mutation을 보내지 않는다.
- fa5e7bd: 거점 하위 필드 변경은 최신 snapshot 좌표에 합친다. 명칭 편집이 다른 참가자의 위도 변경을 되돌리지 않음을 검증했다.
- fe36c73: 고정비는 안정된 ID별로 편집한 필드만 최신 값에 합친다. 다른 참가자의 가격/서버 소계/새 비용 행을 보존하며, 로컬에서 삭제한 기존 행만 제거한다. 배열 입력 병합이라는 자연스러운 단위 때문에 약300자 목표를 소폭 초과했다.
- 23d1574: 표시 review와 공식 confirmed_plan이 같은 5필드 target이고 양쪽에 포함된 동일 item_id/item_version이면 현재 items.state가 mentioned/supported여도 공식 확정 초록을 투영한다. 최신 초안의 included_in_plan도 과거 검토안의 확정을 지우지 않는다. item_version이 달라지면 초록이 옮겨지지 않는다. 표 수/과반/확정 알고리즘을 FE에서 계산하지 않는다. 변경 전 초록0개≠2개 실패를 관측한 뒤 통과했다.

Node 회귀: frontend/tests/events.test.js, trip-input.test.js, items.test.js.
최종 전체 suite: node --test frontend/tests/*.test.js **33/33 pass**. 전체 frontend/src/*.js node --check 통과. staged diff 및 파일 소유권 확인.
계약 변경 없음. UI는 ‘현재 방 입력 저장’ 시 직접 편집한 항목만 반영한다는 안내를 추가했다.

부모가 S2 fixture Backend(8000)에서 로그인·입장·두 Kakao 지도 컴포넌트·장소 상세 연결을 관측했다고 전달했다. 이는 부모의 G3 UI 관측이며, 위 새 폼 병합/첫 SSE/색상 수정 전체를 실제 네트워크에서 다시 관측한 결과는 아니다. 위 회귀의 직접 근거는 Node 제어 테스트다.

S2 추가 인계: 이전 fee36dd 다음부터 work/fe 최신 HEAD까지 순서대로 통합한다. 마지막 HEAD는 최종 응답과 git rev-parse work/fe로 확인한다. S1 push/PR/merge 없음.

추가 실제 모듈 메모리 smoke: Node에서 실제 frontend/src/room.js를 import하고 최소 form DOM/Fetch/EventSource 대역으로 실행했다. 초기 예산200000 폼 → 서버 예산300000/seq증가 → 첫 onopen 시 GET가 총2회로 증가함 → 종료시각19:00 저장 PATCH가 {day_end_time:"19:00"}만 포함함을 확인했다. PATCH 대기 중 입력을20:00으로 편집한 뒤 응답을 완료해도20:00이 유지되며, 다음 저장은 {day_end_time:"20:00"}만 전송했다. error 출력도 비어 있었다. 이는 실제 모듈의 폼 baseline/콜백 연결 검사이며 실제 브라우저/네트워크 관측은 아니다.
e5e8001 docs(fe): record concurrent form SSE and confirmed color fixes
