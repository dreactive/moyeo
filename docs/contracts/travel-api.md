# FE·BE·AI 공통 계약 v0.2

- 기준: [MVP 설계](../superpowers/specs/2026-11-18-travel-agent-design.md), 2026-11-18 사용자 확정 사항.
- 상태: 구현할 계약. 실제 배포된 endpoint나 생성된 OpenAPI가 아니다.
- 규칙: JSON snake_case, ID 문자열, 시간 ISO 8601(타임존 포함), 날짜 YYYY-MM-DD, 금액 KRW 정수/미확인 null, 이동시간 초·거리 m, 좌표 latitude/longitude.
- 로그인 세션은 같은 origin cookie. 브라우저가 user_id를 임의 지정해 타인의 지지/확인 표를 작성하지 않는다.
- v0.2 변경: HTTP·SSE·제품 DTO는 유지하고 BE/AI 연결을 JSON AgentPort로 분리한다. 각 세션은 상대 폴더 import 없이 개발한다. [3세션 계획](../superpowers/plans/2026-11-18-three-session-plan.md)의 소유권과 통합 절차가 기존 BE·AI 합본 실행 순서보다 우선한다.

## 0. 세션 독립성과 계약 동결

- 이 문서와 [공통 예제](examples/README.md)는 동결된 읽기 전용 기준이다. S1은 frontend/, S2는 backend/, S3는 ai/만 구현한다.
- Backend의 DTO/Protocol은 backend/schemas.py와 backend/ports.py, AI 내부 DTO/Protocol은 ai/contracts.py에 각각 둔다. 서로의 Python 타입 파일을 import하거나 수정하지 않고 같은 JSON 예제로 적합성을 검사한다.
- AI 모델·공급자·시간표·경비 계산은 S3 소유다. Backend는 AgentResult 반영·동의·저장·SSE를 맡고 계산 알고리즘을 복제하지 않는다.
- 상대 구현이 없어도 FE fixture / Backend FixtureAgentPort / AI FakeModelBackend·fixture ToolExecutor로 각각 검증한다. 모드 표시는 유지하며 실제 API/Qwen 검증과 구분한다.
- 계약 수정은 S2 통합 담당자가 영향 세션과 맞춘 뒤 한 번 반영한다. 작업 세션이 단독으로 필드명·enum을 바꾸지 않는다.

## 1. 공통 타입

### 1.1 사용자·방·메시지

| 타입 | 필수 필드와 의미 |
|---|---|
| User | id, name, email |
| Member | user_id, name |
| Anchor | label, latitude, longitude. 장소 출처가 있으면 source_ref |
| TripConfig | region, start_date, end_date, transport="car", day_start_time="09:00", day_end_time="18:00", per_person_budget_krw, origin:Anchor/null, destination:Anchor/null, lodging:Anchor/null, fixed_costs:CostLine[] |
| Message | id, room_id, seq, author_id, text, created_at. author는 항상 사람 |
| Versions | participant_version, constraint_version, evidence_version, plan_revision: 각 정수 |
| ConfirmationTarget | Versions의 네 값 + content_hash |

`region`은 국내 지역명. 첫 데모 여수, 기간 2일이다. source_ref는 공급자 결과를 식별하는 내부 참조이며 사용자에게 비밀 키를 포함하지 않는다.

day_start_time/day_end_time은 해당 여행일 Asia/Seoul의 기본 활동 구간이며 사용자 입력으로 바꿀 수 있다. 1일차는 origin→방문지→lodging, 2일차는 lodging→방문지→destination이다. 확인한 개인 귀가 제한이 더 이르면 그 제한을 적용한다. 신규 사용자 입력 CostLine.id는 브라우저가 만든 UUID를 사용하고 저장 후 유지한다.

### 1.2 결정 항목·조건·충돌

| 타입 | 필드 |
|---|---|
| DecisionItem | id, item_version, kind(place/itinerary_change/shared_condition), title, source_message_ids[], included_in_plan:bool, supporter_ids[], opponent_ids[], support_threshold:int, state(mentioned/supported/confirmed), conflict_ids[] |
| Constraint | id, owner_id, key, value, kind(hard/preference), status(needs_owner_confirmation/confirmed/superseded), source_message_ids[] |
| SupportObservation | item_id, item_version, author_id, stance(support/oppose/withdraw/unclear), source_message_id |
| Conflict | id, type(time/budget/opening_hours/personal_constraint/preference), explanation, affected_item_ids[], base_versions:Versions, blocking:bool, status(open/resolved), options:ConflictOption[] |
| ConflictOption | id, label, effect_summary, requires_owner_id:string/null, effect:object |
| Question | id, owner_id:string/null, field, target_ref:string/null, text, related_item_ids[], status(open/answered), answer:any/null, answered_by:string/null |

Backend가 state를 계산한다. FE가 임의로 색상 판정하지 않는다. `confirmed`는 현재 화면에 표시한 confirmed snapshot과 일치하는 항목만 가능하다. 새 초안을 보면 미확정 상태를 표시하고 기존 확정안은 별도 열람한다.

개인 Constraint는 본인 확인 대상이며 다수결로 완화하지 않는다. DecisionItem의 공유 조건은 장소 선택·방문 순서 등 공동 계획 결정에 해당한다.

ConflictOption.effect는 다음 중 하나다: `{kind:"drop_visit",item_id}`, `{kind:"reorder_visits",date,ordered_item_ids}`, `{kind:"replace_place",item_id,new_place_ref}`, `{kind:"change_constraint",constraint_id,new_value,owner_id}`. Backend는 해당 옵션이 만들어진 기반 버전에서 선택을 적용하고 재계산한다.

Question.field는 origin/destination/lodging/menu_selection/visit_duration/constraint_value/support_target 중 하나다. 공유 질문(owner_id=null)은 참가자가 답할 수 있고 개인 질문은 본인만 답한다. answer는 각각 Anchor, `{menu_id,quantity,scope}`, `{stay_minutes}`, `{value}`, `{item_id}` 형태다. target_ref는 메뉴/체류시간/지지의 대상 item_id 또는 수정할 constraint_id이며, 거점 입력은 anchor:origin/destination/lodging이다. support_target 답변은 원래 발언자의 대상 확인이며 다른 사람의 지지를 새로 만들지 않는다.

### 1.3 조회 근거·도구 데이터

| 타입 | 필드 |
|---|---|
| PlaceRef | id(내부), name, address, latitude, longitude, provider_refs:object |
| Menu | id, name, price_krw:int/null, price_text, serving_basis:string/null, evidence_id |
| OpeningHours | raw_text, intervals:array/null, holiday_text:string/null, evidence_id |
| Evidence | id, provider, provider_record_id, source_url, field, raw_value, normalized_value, status(api_observed/missing/user_provided/estimated), retrieved_at, provider_updated_at:string/null, mode(live/fixture), match_status(matched/ambiguous/unmatched) |
| PlaceDetails | place:PlaceRef, menus:Menu[], opening_hours:OpeningHours/null, evidence:Evidence[] |
| RouteLeg | from_ref, to_ref, distance_m:int, duration_seconds:int, toll_krw:int/null, polyline:{latitude:number,longitude:number}[], evidence_id |

`api_observed`는 API에 값이 있었다는 뜻이며 실시간 현장 보증이 아니다. 문자열 가격·복수 운영시간·휴무일은 원문을 보존하고 확실히 해석할 수 있을 때만 normalized_value에 담는다. 메뉴 미등록은 menus=[]이고 가격0이 아니다. 테스트 fixture는 live로 표시하지 않는다.

### 1.4 일정·비용·확인

| 타입 | 필드 |
|---|---|
| Visit | item_id, place_ref, date, start_at, end_at, stay_minutes:int, selected_menu_ids[], assumptions[] |
| TravelDay | date, visits:Visit[], route_legs:RouteLeg[] |
| CostLine | id, category(lodging/intercity_transport/meal/admission/car/other), scope(shared/per_person), owner_id:string/null, description, unit_price_krw:int/null, quantity:number, subtotal_krw:int/null, paid:bool, evidence_id:string/null, assumption:string/null |
| CostSummary | lines:CostLine[], known_total_krw:int, total_krw:int/null, per_person_krw:object, paid_krw:int, paid_by_user_krw:object, remaining_budget_krw:object, planned_balance_krw:object, unknown_line_count:int, estimated_line_count:int |
| PlanItemSnapshot | id,item_version,kind,title,source_message_ids[],place_ref:string/null. 검토 시점의 항목 내용 복사 |
| PlanSnapshot | plan_revision, participant_version, constraint_version, evidence_version, content_hash, selected_item_ids[], item_snapshots:PlanItemSnapshot[], days:TravelDay[], cost:CostSummary, validation(ready/needs_input/conflict), blocking_conflict_ids[], confirmation_target:ConfirmationTarget |
| Confirmation | user_id, target:ConfirmationTarget, stance(confirm/withdraw), created_at |
| AgentStatus | run_id:string/null, state(idle/running/needs_input/done), label |

금액은 코드로 계산한다. shared는 unit_price×quantity를 방 전체 소계로 만들고 참가자에게 균등 분담한다. per_person은 owner_id가 있으면 그 사람에게만 unit_price×quantity, null이면 모든 참가자에게 각각 같은 금액을 적용한다. subtotal_krw는 항상 방 전체 금액이므로 per_person/owner_id=null에서는 인원수도 곱한 값이다. 원 단위 나머지는 user_id 정렬 순서로 1원씩 배분한다. 포함해야 할 비용이 미확인이면 total_krw=null이고 known_total_krw에는 알려진 소계만 남긴다. per_person_krw는 기지출+예정 전체액이고 paid_by_user_krw는 paid=true의 분담액만 합한다.

remaining_budget_krw는 **사용자 예산−기지출**(앞으로 쓸 수 있는 금액), planned_balance_krw는 **사용자 예산−기지출을 포함한 전체 계획액**(계획 반영 후 여유)이다. 예산20만원/기지출8만원/미지출 예정7만원이면 각각12만원/5만원이다. 필요한 금액이 미확인이면 해당 계산값은 null이다. 이것은 모델이 가격을 생성하는 규칙이 아니다.

## 2. 방 스냅샷과 상태 갱신

`RoomSnapshot` 필드:

```text
room_id, title, invite_code, seq, config:TripConfig, members:Member[],
versions:Versions, messages:Message[], items:DecisionItem[], constraints:Constraint[],
current_plan:PlanSnapshot/null, review_plan:PlanSnapshot/null, active_target:ConfirmationTarget/null,
confirmed_plan:PlanSnapshot/null, confirmations:Confirmation[],
conflicts:Conflict[], questions:Question[], agent_status:AgentStatus
```

스냅샷 messages는 최근 50개이며 이전 근거 메시지는 메시지 API로 조회한다. seq는 방 이벤트의 증가 번호이며 메시지에도 별도 seq가 있다. plan_revision은 계획 내용이나 실질적 근거가 바뀔 때 증가하고, 단순 대화·장소 열람은 계획 버전을 올리지 않는다. 참가자·조건·근거 변경은 해당 version을 올린다. 확인 대상의 어느 값이든 바뀌면 이전 확인 표를 재사용하지 않는다.

current_plan은 최신 초안, review_plan은 active_target에 대응하는 불변 검토 스냅샷이다. active_target이 있으면 review_plan.confirmation_target과 반드시 같다. 검토 중 새 초안이 생겨도 current_plan만 바뀌고 review_plan은 유지한다. 이때 확인은 최신 초안 번호가 아니라 review_plan의 대상과 비교한다. 참가자·조건·실질적 근거가 바뀌면 기존 검토 대상과 확인 표를 종료하고 새 대상에서 다시 시작한다. 새 안으로의 단순 순서 변경 제안은 기존 검토를 자동 교체하지 않는다.

과거/검토 계획의 항목명·item_version은 해당 item_snapshots로 표시한다. 현재 items의 수정된 문구로 과거 확정안을 다시 그리지 않는다. content_hash는 항목 스냅샷·일정·비용 가정·실질 근거를 정규화한 내용에 SHA-256을 적용해 Backend만 계산한다. 지지/확인 인원·작업상태·단순 재조회 시각은 내용 해시에 넣지 않는다. 같은 실질 값의 재조회만으로 evidence_version이나 확인 대상을 바꾸지 않는다.

## 3. HTTP endpoint

별도 표시가 없으면 JSON 응답 200, 생성 201, Agent 작업 접수 202를 사용한다. 복잡한 오류 분류는 설계하지 않는다. 미정 정보는 Question/Evidence/Conflict 같은 기능 상태로 표현한다.

| 메서드와 경로 | 요청 | 응답 / 동작 |
|---|---|---|
| POST /api/auth/register | name,email,password | User + session cookie |
| POST /api/auth/login | email,password | User + session cookie |
| POST /api/auth/logout | 없음 | {ok:true} |
| GET /api/auth/me | - | User |
| GET /api/health | - | DB 접근 가능 시 {status:"ok"}, 불가 시 503 {status:"unavailable"}. 모델·공급자 준비 상태와 별개 |
| POST /api/rooms | title + TripConfig 각 필드 | RoomSnapshot + 입장한 참가자 |
| POST /api/rooms/join | invite_code | RoomSnapshot |
| GET /api/rooms/{room_id} | - | RoomSnapshot |
| PATCH /api/rooms/{room_id}/trip | 수정할 TripConfig 필드 | RoomSnapshot. 재계획 입력이며 과거 확정안은 수정하지 않음 |
| GET /api/rooms/{room_id}/messages | after_seq:int=0 | {messages:Message[],last_seq:int} |
| GET /api/rooms/{room_id}/messages/{message_id} | - | Message. 근거 메시지 이동용 |
| POST /api/rooms/{room_id}/messages | text | Message. 즉시 저장/전달 후 Agent 비동기 처리 |
| PATCH /api/rooms/{room_id}/constraints/{constraint_id} | value | Constraint. 본인만 수정 |
| POST /api/rooms/{room_id}/constraints/{constraint_id}/confirm | 없음 | RoomSnapshot. 본인 조건 확인 후 관련 재계산 |
| POST /api/rooms/{room_id}/questions/{question_id}/answer | value | RoomSnapshot. 질문의 대상 필드에 입력값을 반영하고 관련 Agent 작업 실행 |
| GET /api/rooms/{room_id}/places/{place_ref} | - | PlaceDetails. 개인 열람은 공동 선택 상태를 변경하지 않음 |
| POST /api/rooms/{room_id}/conflicts/{conflict_id}/select | option_id | {run_id,base_versions:Versions}. 초안 재계산이며 확인 표 생성 아님 |
| POST /api/rooms/{room_id}/agent-runs | reason:"manual_replan" | {run_id,base_versions:Versions}，202 |
| POST /api/rooms/{room_id}/plan/confirm | target:ConfirmationTarget | RoomSnapshot. 첫 확인이 현재 대상을 고정. 동일 대상 전원 확인 후 확정 |
| POST /api/rooms/{room_id}/plan/withdraw | target:ConfirmationTarget | RoomSnapshot. 본인 확인 표만 처리 |
| POST /api/rooms/{room_id}/plan/activate | plan_revision:int | RoomSnapshot. 새 안으로 명시적 전환, 기존 대상 종료 및 공식 확인 표 초기화 |
| GET /api/rooms/{room_id}/events | Last-Event-ID 선택 | text/event-stream. 사용자용 변경 알림 |
| GET /api/dev/rooms/{room_id}/traces | run_id 선택, X-Dev-Token 필수 | {runs:RunTrace[]} |

place_ref는 현재 방의 조회 결과 또는 fixture라고 표시한 데이터에서 나온 값이어야 한다. 이 API는 임의 웹페이지 수집 지시를 받지 않는다. 명시적 재검토나 전체 초안 재생성은 manual_replan으로 요청하고, 일상적인 새 조건 변화는 자동 실행한다.

공개 배포에서는 같은 origin의 Vercel `/api/*`가 PC 서버로 중계한다. API 응답과 오류는
`Cache-Control: no-store`이며 `COOKIE_SECURE=1`은 host-only HttpOnly SameSite=Lax cookie에
Secure를 추가한다. `PUBLIC_REQUESTS_PER_MINUTE` 기본 60은 단일 프로세스의 전역 rolling
60초 POST/PUT/PATCH/DELETE 예산이다. 초과 요청은 handler 실행 전 429와 `Retry-After: 60`으로
거절한다. GET/SSE는 이 예산을 소비하지 않는다. 0은 제한 해제다.
공개 PC 서버는 `SERVE_FRONTEND=0`으로 API만 제공하고, 기존 로컬 화면 기본값은 1이다.
[무료 ngrok 운영 설정과 인수 확인](../deployment/vercel-ngrok.md)을 따른다.

## 4. SSE

방마다 EventSource 연결 하나를 사용한다. 각 이벤트는 id: seq와 JSON data를 포함한다.
연결 즉시, 이후 15초마다 `: keepalive` comment를 보낸다. comment는 이벤트 ID를 바꾸지 않는다.

| event | data | FE 동작 |
|---|---|---|
| message.created | {room_id,seq,message:Message} | message.id로 중복 제거 후 추가 |
| room.updated | {room_id,seq,changed:string[]} | RoomSnapshot 조회 후 관련 공동 화면 함께 갱신 |
| agent.status | {room_id,seq,status:AgentStatus} | 작업 상태 라벨 갱신. 사람 채팅에 AI 메시지 삽입 안 함 |
| plan.confirmed | {room_id,seq,target:ConfirmationTarget} | RoomSnapshot 조회 후 초록/확인 인원 갱신 |

처음 열거나 연결을 복원하면 최신 스냅샷을 조회한다. 알림 도착만으로 관련 데이터가 모두 반영됐다고 간주하지 않는다. token·모델 후보·tool trace는 사용자 이벤트에 포함하지 않는다.

## 5. Agent와 Backend 연결 계약

두 세션 사이에는 JSON 직렬화 가능한 dict/list/scalar만 전달한다. Backend는 자신의 AgentPort를 사용하고 ai/contracts.py를 import하지 않는다. AI는 Backend/FastAPI/DB를 import하지 않는다.

```python
# backend/ports.py — S2 소유. AI의 클래스 import가 필요 없는 구조적 경계.
class AgentPort(Protocol):
    async def run(self, task: dict, emit_trace: Callable[[dict], Awaitable[None]]) -> dict: ...
    async def execute_tool(self, name: str, arguments: dict, context: dict) -> dict: ...
    async def aclose(self) -> None: ...

# ai/runtime.py — S3 소유. 실제 연결 시에만 Backend가 지연 import.
def create_runtime(config: dict) -> AgentRuntime: ...
```

AgentRuntime은 같은 run/execute_tool/aclose 메서드를 제공한다. config는 model_backend(fake/local_qwen), provider_mode(fixture/live), base_model_path, adapter_path, env_file 경로를 받는다. fake/fixture에서는 GPU·모델·외부 API가 필요하지 않으며 torch는 local_qwen 선택 때만 로딩한다.

create_runtime은 작업마다 호출하지 않고 실행 환경의 lifespan에 한 번 만든다. run 안에서는 task의 room_id/config/observations로 작업별 도구 참조 문맥을 만든다. execute_tool의 context는 `{room_id,config,observations}`다. 방/작업의 장소·Anchor를 전역 mutable registry에 섞지 않는다. 공유하는 것은 모델 인스턴스와 모델 연산 직렬화 장치다.

S2는 backend/adapters/fixture_agent.py의 FixtureAgentPort를 먼저 구현하고 AI 코드 없이 API를 완성한다. 통합할 때 backend/adapters/local_ai.py 한 곳에서 create_runtime을 지연 import한다. AgentPort.run에 넣을 task와 반환값은 각각 아래 AgentInput/AgentResult의 JSON이다. Backend의 단일 방 작업 큐와 AI의 모델 직렬화는 별도 책임이며 서로 작업을 다시 enqueue하지 않는다.

아래는 **AI 내부 인터페이스**다. S2가 이 파일을 수정하거나 이 타입의 구현을 기다릴 필요가 없다.

```python
class ModelBackend(Protocol):
    def generate_json(self, request: dict) -> dict: ...
    def score_candidates(self, context: dict, candidates: list[dict]) -> list[float]: ...

class ToolExecutor(Protocol):
    async def execute(self, name: str, arguments: dict) -> dict: ...

async def run_agent(
    task: AgentInput,
    model: ModelBackend,
    tools: ToolExecutor,
    emit_trace: Callable[[dict], Awaitable[None]],
) -> AgentResult: ...
```

| 타입 | 내용 |
|---|---|
| ToolObservation | tool_name,arguments:dict,result:dict,observed_at,source_refs:string[] |
| UserSelection | conflict_id,option_id,effect:ConflictOption.effect,base_versions:Versions |
| AgentInput | run_id,room_id,base_versions:Versions,goal,recent_messages:Message[],members:Member[],config:TripConfig,constraints:Constraint[],items:DecisionItem[],questions:Question[],user_selection:UserSelection/null,current_plan:PlanSnapshot/null,observations:ToolObservation[] |
| AgentResult | run_id,room_id,base_versions:Versions,constraint_proposals:dict[],support_observations:SupportObservation[],item_proposals:dict[],plan_draft:dict/null,observations:ToolObservation[],conflicts:Conflict[],questions:Question[],completion(done/needs_input/unsupported),last_processed_message_id:string/null |

Backend가 AgentResult를 저장 타입으로 변환하고 base_versions를 확인한다. AI는 최종 Confirmation이나 confirmed 상태를 생성할 수 없다. plan_draft에는 Backend가 배정할 version/hash를 넣지 않고 selected_item_ids/days/cost/validation 내용만 담는다. 새 item/constraint ID를 배정하고 참조를 해결한 뒤 item_snapshots와 계획 버전을 만든다.

runner는 실제 도구 반환값을 ToolObservation으로 수집해 AgentResult.observations로 전달한다. Backend는 이를 공급자 보관 조건에 맞는 메모리/저장 경계에 적용하고 PlaceDetails·Evidence 참조를 제공하며, 다음 AgentInput.observations에 필요한 결과를 넣는다. trace는 진단용이며 제품 데이터 전달 통로로 사용하지 않는다.

충돌 선택 endpoint는 저장된 ConflictOption.effect를 UserSelection으로 복사해 AgentInput에 넣는다. 사용자가 선택한 ‘제외/순서변경/장소교체’를 자유 문장으로 다시 추측하지 않는다. base_versions와 대상 ID가 맞는 선택을 실행기가 우선 반영한 뒤 경로·일정·경비를 재계산한다.

단, change_constraint는 예외다. 해당 owner_id 본인만 선택할 수 있고, 선택만으로 확인된 필수 조건을 바꾸지 않는다. 본인의 조건 수정·확인 카드로 연결하고 `/constraints/{constraint_id}/confirm`이 완료되기 전에는 이전 확인 조건을 완화해 일정에 적용하지 않는다. UserSelection을 받았다는 이유로 실행기가 이 확인을 생략해서는 안 된다.

constraint_proposals의 항목은 `{owner_id,key,value,kind,source_message_ids,replaces_constraint_id:null|string}`다. item_proposals는 `{client_ref,existing_item_id:null|string,kind,title,source_message_ids}`다. 임시 client_ref는 한 결과 안에서만 유효하고 Backend가 실제 ID로 변환한다. 도구가 돌려주는 PlaceRef.id는 ToolExecutor가 생성하며 LLM이 임의 생성하지 않는다.

## 6. 도구 레지스트리

| 도구명 | arguments | result / 용도 |
|---|---|---|
| search_places | query:str,region:str,category:str/null | {places:PlaceRef[]} |
| get_place_details | place_ref:str | PlaceDetails. 같은 매장 메뉴·영업시간 매칭 |
| get_car_route | from_ref:str,to_ref:str,departure_at:str/null | RouteLeg |
| build_itinerary | visits:dict[],anchors:dict,constraints:dict[],route_legs:RouteLeg[] | {days:TravelDay[],conflicts:Conflict[],questions:Question[]}. 실제 구간 값으로 시간표 조립 |
| calculate_costs | lines:CostLine[],member_ids:str[],budget_by_user:dict | CostSummary |

get_car_route의 고정 거점 참조는 anchor:origin, anchor:destination, anchor:lodging이다. 그 외에는 PlaceRef.id를 쓰며 ToolExecutor가 일관되게 해석한다. build_itinerary의 visit은 `{item_id,place_ref,date,preferred_start_at:null|string,stay_minutes,selected_menu_ids}`이며 기존 후보만 참조한다. 기본 체류시간은 assumption에 남기고 사용자가 바꿀 수 있게 한다. 위치·가격 사실은 도구 결과나 사용자 확인값에서만 가져온다.

설계자가 정한 초기 체류시간은 관광지60분, 식사60분, 카페40분이다. 이는 실제 관측이 아닌 사용자 변경 가능한 일정 가정이다. route_legs는 이전 get_car_route 관측에서 참조·해결한 값이며 모델이 이동 초를 생성해 넣지 않는다. detail 질문의 답변과 선택 메뉴/수량은 CostLine 구성의 근거로 사용한다.

## 7. trace 계약

TraceEvent 필드는 `run_id,step,event,call_id:null|string,created_at,payload`다. event는 decision/tool_call/tool_result/state_applied다.

- decision payload: goal,candidates,selected_index,scores,model_mode,base_versions. scores는 비교 점수이며 확률이 아님.
- tool_call payload: tool_name,arguments。
- tool_result payload: tool_name,normalized_result,duration_ms,source_refs. 호출과 결과의 call_id가 같음.
- state_applied payload: applied:bool,summary,versions。
- RunTrace: run_id,room_id,started_at,events[]。

개발자 API로만 출력한다. 모델 내부 추론은 계약에 포함하지 않으며 API key를 payload에 넣지 않는다. 공급자 원문 응답은 기본적으로 영구 저장하지 않는다.

## 8. 공통 검증 예

- 4명 중 제안자와 다른 2명이 같은 item_version을 각각 명시 지지: supporter_ids 3개, state=supported.
- 같은 사람의 지지 3번 반복: 여전히 1명, state=mentioned.
- 3명이 같은 target 확인: 아직 미확정. 4명 모두 확인하고 validation=ready: 계획과 포함 항목 confirmed.
- 시간 충돌: blocking=true, 항목의 conflict_ids에 연결. 노랑을 초록으로 간주할 수 없음.
- 계획 변경: plan_revision 증가, 새 대상의 확인을 다시 받음. 기존 confirmed_plan은 보존.
- 개발 fixture가 같은 DTO를 반환해도 mode=fixture이므로 실제 API 검증 통과는 아님.
