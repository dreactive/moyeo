# Three-Session Parallel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** FE·BE·AI 세 세션이 다른 세션의 코드·API 키·GPU 준비를 기다리지 않고 각자의 기능을 구현·검증하고, 정해진 통합 게이트에서 연결한다.

**Architecture:** S1은 HTTP/SSE 모양의 브라우저 fixture로, S2는 자체 FixtureAgentPort로, S3는 JSON 입력과 fake 모델/fixture 도구로 시작한다. 실제 연결은 동결된 v0.2 계약을 그대로 쓰는 Backend 어댑터 한 곳에서 수행한다. 사용자 기능은 기존 MVP와 같고 개발 순서·환경·소유권만 바꾼다.

**Tech Stack:** S1 HTML/CSS/ES modules; S2 FastAPI/SQLite; S3 순수 Python Agent·httpx·선택적 Qwen/PEFT. 실제 모델 의존성은 AI 세션과 최종 통합 때만 필요하다.

**Spec:** [MVP 설계](../specs/2026-11-18-travel-agent-design.md), [계약 v0.2](../../contracts/travel-api.md), [동결 예제](../../contracts/examples/README.md).

## Global Constraints

- 이번 요청은 **계획 개정**이다. 실제 새 채팅·worktree 생성, 코드 작성, 설치, API 실행, Git 작업을 시작하지 않는다.
- 실제 구현 시 세 세션은 서로 다른 작업 공간·Git index를 쓴다. 같은 checkout에서 동시 checkout/commit하지 않는다.
- 상대 폴더를 import하거나 수정하지 않는 상태에서 독립 완료가 가능해야 한다.
- 제품 정책·DTO·색상·확인 단위·가격/시간 실제 조회 요구는 변경하지 않는다.
- 실제 API·Qwen 성공과 fixture/fake 성공을 구분한다. 키가 없더라도 독립 개발·테스트는 진행한다.
- 공유 DTO를 여러 세션이 수정하는 새 Python 패키지는 만들지 않는다. 각자 자신의 타입을 두고 같은 JSON 계약으로 대조한다.
- 구현을 요청받은 뒤 로컬 개인 small-commits 규칙을 적용한다. 약300자 실행 로직 단위의 동작·검증·커밋을 유지한다.

## Review Focus

1. Backend가 ai/contracts.py·모델·공급자에 import 의존해 단독 실행이 막히지 않는가 — S2 B1.
2. FE의 전체 사용자 흐름이 Backend의 endpoint 완성을 기다리는 계획으로 되돌아가지 않는가 — S1 F1-F5 fixture 검증.
3. AI가 DB·로그인·HTTP 서버 없이 동일 AgentInput→AgentResult를 만들 수 있는가 — S3 A0/A5.
4. 같은 Anchor/PlaceRef 문자열을 가진 두 방의 관측이 섞이지 않는가 — S3 A2/A4, S2 통합.
5. 공유 파일·DB·환경·GPU·확인 표 검증이 세 세션 사이에서 충돌하지 않는가 — 아래 소유권과 G1-G4.

## 1. 세션 배정과 기다리지 않는 방법

| 세션 | 독점 작업 | 개발 중 대체물 | 독립 실행·완료 기준 |
|---|---|---|---|
| **S1 FE** | frontend/** | 브라우저 fixture transport·가짜 SSE | BE 없이 로그인/방/대화/색상/확인/충돌/두 지도 자리·경비·trace 렌더링 시나리오 검증 |
| **S2 BE + 통합 담당** | backend/** | Backend 소유 FixtureAgentPort | ai/가 없어도 계정·방·메시지·SSE·동의·버전·질문·결과 반영·개발자 API 검증 |
| **S3 AI** | ai/** | FakeModelBackend·fixture ToolExecutor | BE·FE 없이 입력 JSON→추출/판단/도구/계산/결과 JSON 및 trace 검증 |

각 실행 계획: [S1 FE](2026-11-18-frontend.md), [S2 BE](2026-11-18-backend.md), [S3 AI](2026-11-18-ai.md). 기존 [BE·AI 합본](2026-11-18-backend-ai.md)은 전환 안내만 남기며 새 실행 기준으로 사용하지 않는다.

## 2. 파일 소유권

| 경로 | 변경 권한 | 다른 세션의 사용 |
|---|---|---|
| frontend/** | S1 | 읽기·통합 시 제공만 |
| backend/** | S2 | 공개 HTTP 계약만 사용 |
| ai/** | S3 | 통합 시 공개 create_runtime/AgentPort만 사용 |
| docs/verification/frontend.md | S1 | 다른 세션 읽기 전용 |
| docs/verification/backend.md, integration.md | S2 | 다른 세션 읽기 전용 |
| docs/verification/ai.md | S3 | 다른 세션 읽기 전용 |
| docs/contracts/**, docs/testing/mvp-checklist.md, MVP 설계·계획 | 동결. 변경 조정자는 S2 | 임의 변경 금지. 제안은 자기 검증 기록에 남김 |
| README.md, .gitignore, 향후 루트 공용 설정 | S2 통합 시 | S1/S3는 각 폴더 README/설정만 수정 |
| submission/**, 기존 PDF/대회 원본 | 세 세션 모두 변경하지 않음 | S3가 읽기 참조 |

다른 세션의 파일에 문제가 있어도 직접 고치지 않는다. 관측한 입력/출력과 재현 방법을 자신의 검증 기록에 적어 소유자에게 전달한다. 공통 체크리스트를 세 사람이 동시에 체크하지 않는다.

## 3. 공통 계약을 지금부터 읽기 전용으로 사용

G0 계약 기준은 이미 문서에 준비돼 있다. 세 세션은 [예제 폴더](../../contracts/examples/README.md)를 읽고 자기 테스트용 복사·변형을 만든다.

- FE: RoomSnapshot/PlaceDetails/RunTrace와 HTTP/SSE DTO.
- BE: AgentInput 직렬화, AgentResult 반영, ToolObservation, UserSelection.
- AI: 같은 AgentInput 소비, 같은 AgentResult 반환, 같은 trace event.
- 임시 client_ref·입력 필요·미지원·오래된 결과·충돌 선택도 공통 예제에서 출발한다.
- 예제 변경 없이 기능이 구현 가능한 동안 계약 수정 때문에 다른 세션을 기다리지 않는다.

변경이 필요하면 `제안 필드 / 기존 값 / 새 값 / 영향 세션 / 기존 계약을 유지할 대안`을 소유 보고서에 적는다. S2가 영향을 확인한 뒤 버전과 예제를 같이 갱신한다. 변경된 계약을 공유하기 전 각자 다른 이름으로 임시 확정하지 않는다.

## 4. 독립 환경과 공유 자원

| 항목 | S1 | S2 | S3 |
|---|---|---|---|
| 설정/의존성 | frontend/README.md, 공개 지도 키 설정 | backend/requirements.txt, backend/.env.example | ai/requirements.txt, 선택적 모델 의존성, ai/.env.example |
| 환경 | 별도 Python 정적 서버면 충분 | backend/.venv | ai/.venv |
| pytest 설정 | 필요 시 frontend/ 안에만 | backend/pytest.ini | ai/pytest.ini |
| 실행 | 5173, fixture | 8000, AGENT_MODE=fixture | CLI, 서버 포트 불필요 |
| 결과·임시 파일 | frontend/.artifacts | backend/.data, backend/.artifacts | ai/.artifacts |
| 비밀 키 | 서버 비밀 키 없음 | 세션/개발자 토큰, 실제 연결 전 AI 키 불필요 | 모델 경로·공급자 API 키 |
| 실제 GPU·공급자 probe | 사용 안 함 | G4 전 사용 안 함 | **독립 개발 중 S3 단독 사용** |

각 worktree의 DB·출력·가상환경을 공유하지 않는다. 학습 가중치·공통 모델 캐시는 S3가 준비하고 나머지 세션은 임의 다운로드/변경하지 않는다. 최종 통합 시 S3 CLI의 실제 모델 실행을 종료한 뒤 S2가 한 모델 인스턴스로 실행한다.

각 세션은 자기 폴더의 .gitignore에서 비밀 .env·환경·검증 산출물을 처음부터 제외한다. 이 로컬 제외 설정 때문에 루트 파일을 공동 수정하거나 S2의 최종 통합을 기다리지 않는다.

Backend 환경에는 AI 의존성을 선행 설치하지 않는다. G2는 AI의 fake/fixture runtime만 연결해 확인하고, G4에서 실제 모델 실행 환경에 Backend 의존성을 더해 한 환경으로 묶는다. 선언 의존성 합치기·최종 lockfile·루트 설정은 S2 한 세션이 처리한다.

## 5. 작업 공간과 Git 전달 — 실제 구현 요청 후 적용

- [ ] S2가 현재 checkout/원격/develop 상태를 확인하고 세 작업 공간의 공통 시작 commit을 고정한다. Git 이력이 없다면 기존 checkout과 원격을 먼저 확인한다.
- [ ] S1 work/fe, S2 work/be, S3 work/ai처럼 서로 다른 작업 branch/worktree를 사용한다. 실제 생성 경로는 host와 권한에 맞춰 정하며 이 문서가 worktree를 생성한 것은 아니다.
- [ ] Git에서 제외된 AGENTS.md·.local 개인 스킬은 worktree에 자동 복사되지 않으므로, 각 작업 공간에서 로컬 전용으로 읽을 수 있게 준비한다. 공유 커밋에 추가하지 않는다.
- [ ] 각 세션은 자기 경로만 작은 동작 단위로 검증·커밋한다. 세 세션이 같은 develop branch/공유 index를 동시에 commit·push하지 않는다.
- [ ] 기능 인계는 commit SHA/범위 + 계약 버전 + 검증 명령/결과 + 미완료 제약으로 한다. S2가 통합 공간에서 순서대로 가져와 확인한다.
- [ ] 최종 develop push와 master 대상 PR 갱신은 S2만 수행한다. 자동 merge는 하지 않는다. 개인 기본 develop 전달 규칙은 병렬 작업의 통합 마감에서 한 번 적용한다.

처음 필요한 공통 작업은 checkout/격리 준비뿐이다. 공급자 키 발급·모델 로딩·화면 완성을 공통 출발 조건으로 만들지 않는다.

## 6. 병렬 진행과 통합 게이트

| 구간 | S1 | S2 | S3 | 대기 조건 |
|---|---|---|---|---|
| G0 이후 즉시 | F1-F5를 fixture로 구현 | B1-B4를 FixtureAgentPort로 구현 | A0-A5를 fake/fixture로 구현, 가능한 live probe 병행 | 다른 세션 코드 불필요 |
| G1 독립 완료 | 화면 시나리오·자체 기록 | HTTP/SSE·도메인·자체 기록 | JSON 입출력·도구/계산·자체 기록 | 각자 완료만 판단 |
| G2 BE↔AI | fixture 개선 계속 가능 | AI fake runtime을 실제 어댑터로 연결 | factory/JSON/trace 확인 지원 | S2/S3의 공개 경계만 필요 |
| G3 FE↔BE | 같은 origin live 화면 연결 | fixture Agent로 서비스 제공 | 모델/공급자 검증 계속 가능 | S1/S2만 필요, GPU 불필요 |
| G4 전체 live | 4인 데모·화면 검증 | 단일 서버/동의/결과 통합 | 실제 Qwen·실API 인계 | 실제 키·모델·데이터 확보 필요 |

G2와 G3는 서로 선행 조건이 아니다. G4만 실제 모델/공급자와 세 구현이 모두 필요하다. 독립 완료를 최종 통합 완료로 표시하지 않는다.

### G1: 각 세션 독립 완료

- [ ] S1은 다른 폴더를 참조하지 않는 fixture 서버에서 F1-F5 시나리오를 실행했다.
- [ ] S2는 ai/가 없는 환경에서 가짜 Agent로 모든 Backend 테스트를 실행했다.
- [ ] S3는 backend/·frontend/가 없는 환경에서 fake/fixture CLI와 AI 테스트를 실행했다.
- [ ] 세 보고서는 계약 v0.2와 실행 모드를 명시한다. 가짜 결과를 live 통과로 표시하지 않는다.

### G2/G3: 경계 연결

- [ ] S2는 `create_runtime({"model_backend":"fake","provider_mode":"fixture"})`를 lifespan에 한 번 연결하고 AgentPort의 JSON·trace·close를 검사했다.
- [ ] execute_tool의 context로 Anchor/PlaceRef와 관측을 복원하며 두 방의 데이터가 섞이지 않는다.
- [ ] FE는 Backend가 같은 origin으로 제공하는 화면에서 계정·POST·SSE·확인·충돌·질문을 검증했다. 별도 CORS/프록시 인프라를 선행 요구하지 않는다.
- [ ] 수정은 각 파일 소유자가 하고 S2가 통합한다. 실제 AI 키가 없어도 G2/G3는 끝낼 수 있다.

### G4: 실제 기능 마감

- [ ] S3의 여수 실API/실제 Qwen 결과와 남은 제약을 S2가 인수했다.
- [ ] 실제 모델은 한 프로세스/한 인스턴스로만 구동하며 CLI와 중복 GPU 점유하지 않는다.
- [ ] C01-C47의 최종 관측 근거를 S2가 취합해 [공통 검증표](../../testing/mvp-checklist.md)에 반영했다.
- [ ] 귀가 조건 → 충돌 `!` → 선택 → 실제 경로/경비 갱신 → 같은 여행안 전원 확인 → 초록까지 검증했다.

## 7. 세션 시작 시 전달할 지시문

다음 지시문은 사용자가 별도 세션을 시작할 때 복사할 수 있는 인계문이다. 현재 세션 3개를 생성하거나 구현을 시작한 것은 아니다.

### S1 FE

> 공통 MVP 설계, 계약 v0.2, 동결 예제와 frontend 계획을 읽고 S1을 맡아 구현한다. frontend/**와 docs/verification/frontend.md만 수정한다. Backend가 없어도 fixture transport로 F1-F5를 끝낸다. 공용 문서/다른 폴더/루트 설정을 수정하지 말고 계약 변경 제안은 자기 기록에 남긴다. 실 API 검증과 fixture를 구분한다. 같은 checkout의 develop에서 다른 세션과 동시에 Git 작업하지 않는다. 작은 기능별로 검증·커밋하고 인계 SHA/명령/결과/남은 제약을 보고한다.

### S2 BE·통합

> 공통 설계, 계약 v0.2, 동결 예제와 backend 계획을 읽고 S2를 맡아 구현한다. backend/**와 자기 검증 기록을 소유한다. AI 코드 import 없이 FixtureAgentPort로 B1-B4를 끝낸다. ai/**와 frontend/**를 고치지 않는다. 공용 문서/루트 파일 조정과 최종 통합은 S2만 담당한다. G2는 AI fake runtime, G3는 fixture Agent 화면 연결로 GPU 없이 검증한다. 실제 모델/키는 G4에서 연결한다. 격리된 작업 공간·작은 검증 커밋을 유지하고 develop 통합/push와 master PR은 한 곳에서 처리한다.

### S3 AI

> 공통 설계, 계약 v0.2, 동결 예제, 공급자 문서와 ai 계획을 읽고 S3를 맡아 구현한다. ai/**와 docs/verification/ai.md만 수정한다. BE/FE/DB import 없이 fake/fixture JSON 재생을 먼저 끝내고 모델·실API는 별도 검증한다. 공개 경계는 ai.runtime.create_runtime과 AgentRuntime.run/execute_tool/aclose다. 모델은 한 번 로딩하고 도구 문맥은 방/작업마다 복원한다. 같은 GPU의 실제 모델/공급자 probe는 S3가 담당하며 통합 때 실행을 종료해 인계한다. 계약/루트 문서/다른 폴더는 고치지 않는다. 작은 기능별 검증·커밋과 결과 JSON/명령/키 준비사항/제약을 보고한다.

## 8. 계획 검증 기준

- [ ] 각 세션 계획에는 자기 파일만 수정하는 독립 완료 경로와 검증 명령이 있다.
- [ ] 모든 DTO/endpoint/AgentPort는 v0.2와 일치하며 같은 JSON 예제를 읽는다.
- [ ] 공용 파일·실제 GPU·최종 develop push의 단일 소유자가 정해져 있다.
- [ ] ‘상대 구현 완료 후 시작’ 대신 ‘테스트 대역으로 시작, 게이트에서 교체’가 모든 단계에 적용된다.
- [ ] 최초 47개 기능 기준을 없애지 않고 독립 검증/통합 검증의 증거만 분리한다.

이 문서의 체크는 미래 구현·통합 완료 표시다. 현재 작성한 것은 계획과 계약 예제이며 제품 동작 검증은 미실행이다.
