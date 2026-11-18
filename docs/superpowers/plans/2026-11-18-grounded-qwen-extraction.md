# Grounded Local Qwen Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Approved by the user and implemented on codex/grounded-qwen-extraction; see the verification report and recorded design decisions.

**Goal:** 로컬 Qwen을 유지하며 스키마 기반 장소·조건 추출과 원문 근거 검증을 연결한다.

**Architecture:** 내부 Pydantic 스키마를 JSON 생성 제약과 사후 검증의 공통 기준으로 사용한다. 별도 근거 검증기가 검증된 제안을 기존 AgentResult로 변환하고, Backend는 실패와 정상 빈 결과를 구별한다.

**Tech Stack:** 현재 Python/Transformers/Torch/PEFT, Pydantic v2, 호환성 검증 후 버전을 고정할 LM Format Enforcer, 기존 pytest/FastAPI/Node 테스트.

**Spec:** `docs/superpowers/specs/2026-11-18-grounded-qwen-extraction-design.md` (검토용 초안)

## Global Constraints

- 현재 로컬 Qwen 가중치·tokenizer·adapter 파일과 adapter 비활성 생성 정책 유지. 원격 모델·자동 다운로드 없음.
- 현재 후보 생성 전용 동작 유지. 자동 도구 실행·일정 생성·채점 루프 복원 없음.
- 내부 인용문/추출 스키마는 기존 외부 제안의 필수 필드를 변경하지 않으며 선택적 extraction_report만 추가한다.
- 구조 오류는 최대 1회 재시도. 실패하면 반영/해당 실행의 처리 포인터 전진/자동 재등록 없이 DB 실패 목록에 보존한다. 새 메시지는 실패 목록을 제외해 계속 처리한다.
- 의미 검증 거절은 제안별 기록·제외. 검증된 사실은 반영 가능하며 filtered를 표시한다.
- 각 구현·테스트 단위의 변경 실행 로직을 약 300자 목표로 나누어 검증·커밋한다. 아래 Task 하나는 여러 작은 커밋으로 수행한다.
- 개발은 구현 요청 후 분리된 작업 공간에서 시작한다. 현재 실험 서버/DB/GPU 실행을 임의로 중단하지 않는다. AGENTS.md와 개인 스킬은 제외한다.
- 현재 브랜치는 codex/candidate-generation-only. 구현 전 develop 및 기존 PR과 비교하여 후보 전용 동작을 보존할 통합 경로를 정하고, 사용자 지시 없이 다른 개발 이력을 재작성하지 않는다.

## Review Focus

- 인용문이 긍정이어도 원문 전체가 부정·가정·타인 인용이면 hard 조건으로 바꾸지 않는다. 혼합 의도의 일부 성공이 실패를 가리지 않는다(Task 3/5/7).
- 한글 공백/Unicode 차이는 허용하되 원문에 없는 지점·주소를 생성하지 않는다(Task 3/7).
- 과거 맥락을 새 근거로 재등록하거나 다른 사람/방의 조건을 수정하지 않는다(Task 4/6).
- 잘린 JSON, 중단, 오래된 상태, 새 메시지 도착이 포인터 전진이나 무한 재실행으로 이어지지 않는다(Task 5/6).
- fake/fixture 통과를 실제 Qwen 추출 성공으로 보고하지 않는다(Task 1/7).

## Task 1: 호환성·기준선 확인

**Files:** Read `ai/models/qwen_loader.py`, `ai/models/qwen_generation.py`, `ai/models/local_qwen.py`; draft regression data `ai/eval/extraction_cases.jsonl`; local evidence under `.planning/`.

**Interfaces:** Produces 환경/버전 기록과 32개 익명화 입력의 기대값(kind/title/value/owner/evidence/expected rejection), decoder 채택 판단. 제품 인터페이스 변경 없음.

- [x] 기존 실행 환경의 Python/torch/transformers/peft/pydantic 버전과 GPU 사용 주체를 확인하고 `$TripPython`에 해당 실행 파일의 절대 경로를 지정한다. 현재 서버와 동시에 두 번째 모델을 올리지 않는다.
- [x] 동일 모델·토크나이저에서 작은 스키마의 nullable/enum/array/한글 quote 및 빈 결과를 LMFE로 생성하는 격리 probe를 수행한다. 토큰 제한 종료를 성공으로 취급하지 않는다.
- [x] 자유 생성/제한 생성의 warm 지연과 형식·내용 결과를 비교한다. 핵심 호환 실패 또는 p95 2배 초과는 채택 결정 전에 기록·해소한다.
- [x] 통과한 조합의 정확한 버전을 결정해 이후 의존성 작업에 전달한다. 미통과를 사후 검증만으로 대체하면서 같은 완료 주장하지 않는다.

## Task 2: 공통 추출 스키마와 제한 생성

**Files:** Create `ai/extraction_schema.py`, `ai/models/structured_generation.py`, `ai/tests/test_extraction_schema.py`, `ai/tests/test_structured_generation.py`; modify `ai/requirements.txt`, `ai/requirements-local-qwen.txt`, `ai/models/qwen_generation.py`, `ai/models/fake.py`.

**Interfaces:** `ExtractionBatch`와 `parse_extraction(data: dict) -> ExtractionBatch`; `build_extraction_prefix(tokenizer, schema: dict) -> Callable[[int, torch.Tensor], list[int]]`. phase=extract만 제한 생성하며 actions는 기존 경로를 유지한다.

- [x] `test_extraction_requires_all_lists`, `test_extraction_rejects_extra_and_wrong_type`, `test_assessment_shape_is_strict`, `test_quote_is_required`를 실패 상태로 먼저 작성·확인한다.
- [x] 의존성 선언과 스키마를 작은 동작 단위로 구현한다. 명시적 빈 목록은 허용하고 누락된 목록은 거부한다. 인용문/시각/예산의 유한 길이·타입을 검증한다.
- [x] 제한 생성 연결을 추가한다. tokenizer 데이터 재사용과 호출별 parser 분리, EOS/토큰 상한 종료 감지를 검증한다. fake 출력도 같은 스키마를 따르도록 테스트 대역을 갱신한다.
- [x] Run: `& $TripPython -m pytest -c ai/pytest.ini ai/tests/test_extraction_schema.py ai/tests/test_structured_generation.py ai/tests/test_model_backend.py -q`; 기대: 관련 회귀 전부 PASS. Task 1에서 확정한 버전과 검증 결과를 남긴 뒤 단위별 커밋.

## Task 3: 원문 근거 검증과 제안 변환

**Files:** Create `ai/grounding.py`, `ai/condition_grounding.py`, `ai/tests/test_grounding.py`, `ai/tests/test_condition_grounding.py`; modify `ai/extraction.py`, `ai/assistance.py`.

**Interfaces:** `ground_extraction(batch: ExtractionBatch, task: dict) -> GroundedExtraction`; `GroundedExtraction.proposals: dict`, `.issue_codes: list[str]`, `.rejected_message_ids: list[str]`. `validate_condition(proposal: dict, messages: dict[str, dict], constraints: dict[str, dict]) -> ConditionCheck`은 key별 검증기를 사용한다. `ConditionCheck`는 `accepted: dict | None`, `issue_code: str | None`을 가진다.

- [x] `test_assessments_cover_new_message_ids`에서 assessments의 ID 중복/누락/새 근거 외 참조를 거부한다. 첫 반례: greeting='안녕', key=return_by, value='12:00', 올바른 작성자/메시지 ID여도 rejected여야 한다. 현재 테스트가 통과하는 구멍을 실패 테스트로 고정한다.
- [x] 예산20만원→200000, 16시까지 역 도착→16:00을 통과시킨다. 원문 전체의 부정/가정과 잘린 긍정 quote 조합, 시각 없는 점심, '20만원은 아니야', 타인 인용, 가정, 질문형 제안, 임의 quote/소유자/수정 대상은 거부한다.
- [x] 신규 장소의 정확한 mention_text와 공백 정규화 title을 통과시킨다. 정규화한 title과 mention_text가 다른 경우, 근거에 없는 지점/주소, 원문 밖 quote, 다른 방/이전 메시지를 새 근거로 쓰는 제안은 거부한다. 지역 제안은 POI로 만들지 않는다. key가 제한 문자열인 스키마에서 미지원 key를 정상 파싱한 뒤 unsupported_constraint_key로 거부하는 테스트를 추가한다.
- [x] 기존 규칙 보조도 같은 검증 경로로 통합한다. 새로운 장소 목록을 추가하는 것으로 일반 고유명사 추출을 대체하지 않는다. 기존 확인 조건과 support/version 계약을 보존한다.
- [x] Run: `& $TripPython -m pytest -c ai/pytest.ini ai/tests/test_grounding.py ai/tests/test_condition_grounding.py ai/tests/test_context_extraction.py ai/tests/test_assistance.py -q`; 기대: 핵심 거절/수용 전부 PASS. 동작별 작은 커밋.

## Task 4: 입력 맥락과 프롬프트 정리

**Files:** Modify `backend/services/agent_jobs.py`, `backend/tests/test_agent_jobs.py`, `ai/contracts.py`, `ai/context.py`, `ai/prompts/extract.txt`, `ai/tests/test_context_extraction.py`; add `ai/tests/test_extraction_prompts.py`.

**Interfaces:** AgentInput에 선택적 `conversation_context: list[dict]`; 새 근거 목록은 기존 `recent_messages`. `extraction_context()`는 두 목록을 분리하고 최소 지역/여행 설정과 참조 상태를 제공한다.

- [x] 각 run의 과거 대화가 최대20개, 해당 방만 포함되며 최신 미처리 메시지와 겹치지 않는지 검증한다. 선택 필드가 없는 기존 입력도 동작해야 한다.
- [x] 인사→명시적 빈 결과, 새 고유명사→장소, 지역→region, 부정·질문·타인 발언→hard 조건 거부, 애매한 의견→unclear의 예제를 추가한다. 새 ID·좌표·가격을 모델이 만들지 않도록 한다.
- [x] JSON Schema와 실제 Pydantic 모델의 일치, 과거 맥락을 새 evidence로 거부하는 테스트를 통과시킨다.
- [x] Run: `& $TripPython -m pytest -c backend/pytest.ini backend/tests/test_agent_jobs.py -q`; `& $TripPython -m pytest -c ai/pytest.ini ai/tests/test_context_extraction.py ai/tests/test_extraction_prompts.py -q`; 기대 PASS. BE·AI 계약 관련 커밋을 구분한다.

## Task 5: 추출 결과·오류 상태를 연결

**Files:** Modify `ai/runner.py`, `ai/contracts.py`, `ai/trace.py`, `ai/result.py`, `ai/tests/test_runner.py`, `ai/tests/test_runtime_contract.py`; add `ai/tests/test_extraction_failures.py`.

**Interfaces:** 선택적 `AgentResult.extraction_report = {status, issue_codes, rejected_message_ids, attempts}`. status는 ok/filtered/failed, attempts는 1 또는2. 기존 필수 외부 proposal 구조와 completion enum 유지.

- [x] 잘못된/잘린 출력→1회 재시도→정상 구조의 회복, 두 번 실패→failed + last_processed_message_id=None + 모든 부작용 비어 있음을 검증한다.
- [x] 정상 인사 empty→done, 장소 의도 empty→needs_input, 지역/unclear→needs_input, 근거 없는 조건→filtered + 제안 제외, 유효 장소와 잘못된 조건 혼재→장소만 유지하며 filtered/needs_input을 유지하는 테스트를 작성한다.
- [x] 형식 실패에는 규칙 보조의 성공 대체를 금지한다. 의미 검증 거절에는 추가 모델 호출을 하지 않는다. 진단에는 원시 출력/사고 과정 대신 오류 코드·건수·지연만 넣는다.
- [x] extraction_report는 실제 추출이 실행된 runtime 결과에만 추가한다. empty_result와 기존 fixture 필수키 동일성은 유지하고 새 optional 필드 회귀를 별도로 검증한다.
- [x] Run: `& $TripPython -m pytest -c ai/pytest.ini ai/tests/test_extraction_failures.py ai/tests/test_runner.py ai/tests/test_runtime_contract.py ai/tests/test_trace.py -q`; 기대 PASS. 상태별 작은 커밋.

## Task 6: Backend 실패 반영 차단·진단 표시

**Files:** Modify `backend/services/agent_jobs.py`, `backend/services/agent_apply.py`, `backend/tests/test_agent_jobs.py`, `backend/tests/test_agent_apply.py`, `backend/tests/test_local_ai_bridge.py`, `backend/tests/test_dev_trace.py`, `docs/contracts/travel-api.md`; frontend label 경로는 기존 `frontend/src/room.js:23` 사용.

**Interfaces:** `failed-extraction:<room_id>`는 message_id별 `{issue_codes, attempts, run_id, status:retry_required|recovered}`를 보존한다. `select_extraction_messages(messages: list[dict], processed_id: str | None, failures: dict, retry_failed: bool=False) -> list[dict]`는 일반 요청에서는 실패를 제외한 새 메시지 최대20개, 수동 재계획에서는 실패 포함 재시도 최대20개를 반환한다. 처리 포인터는 방 메시지 순서의 최대 위치로만 갱신한다. report가 없는 AgentPort는 기존 계약대로 처리. failed는 stale과 구분하여 제안 적용/처리 포인터/remaining_messages 자동등록을 차단한다. filtered는 검증된 제안 적용과 포인터 전진을 허용하되 needs_input label에 제외 사실을 표시한다.

- [x] failed 결과에 잘못된 proposal/processed ID가 들어와도 DB가 바뀌지 않는 방어 테스트를 작성한다. 오래된 결과, 20개 배치, 실행 중 새 메시지, 후속 수동 재시도, room isolation을 포함한다. 실패 메시지20개+새 메시지1개에서도 새 메시지는 처리되고 실패 기록20개가 남아야 한다. 과거 실패 메시지를 수동 재처리해도 포인터가 역행하면 안 된다.
- [x] failed에 대해 남은 메시지/버전 변화 자동 재등록을 하지 않는다. 사용자가 이미 추가한 pending 작업은 기존 큐 순서대로 refresh하되 실패를 제외한 새 메시지가 없으면 재호출하지 않는다. 수동 재계획에서는 failed IDs 최대20개를 포함해 검증하고 성공한 ID만 recovered로 바꾼다. 회복 실패는 같은 ID를 자동 재등록하지 않는다. 실패 목록 갱신과 성공 반영/포인터 갱신은 해당 DB transaction에서 일관되게 처리한다.
- [x] 정상 빈 결과·근거 거절·형식 실패·실제 변경을 trace/agent_status.label에서 구분한다. '메시지 형식을 확인하지 못했습니다. 다시 시도해 주세요.'와 '근거를 확인하지 못한 제안은 반영하지 않았습니다.'를 사용한다.
- [x] Run: `& $TripPython -m pytest -c backend/pytest.ini backend/tests -q`; `& $TripPython -m pytest -c backend/pytest.ini backend/tests -q -m integration`; 기대 PASS. 기존 frontend의 label 표시와 SSE 갱신도 확인한다.

## Task 7: 실제 Qwen 재현·문서화·전달

**Files:** Create `ai/eval/extraction_replay.py`, `ai/tests/test_extraction_replay.py`, `docs/verification/grounded-qwen-extraction.md`; finalize `ai/eval/extraction_cases.jsonl`; update `ai/README.md`.

**Interfaces:** 전용 replay는 추출 단계만 실행해 input별 expected/actual, grounded facts, rejected codes, decoder, attempts, token/latency/format metrics를 로컬 JSON으로 기록한다. 도구/방 DB를 수정하지 않는다.

- [x] 평가 집계 테스트를 먼저 작성한다. fake 실행 기록과 local_qwen 실행 기록을 분리하고 모델 실패를 fake 성공으로 대체하지 않는다.
- [x] 전체 AI suite, Backend suite, 관련 frontend Node tests를 실행한다. 예: `& $TripPython -m pytest -c ai/pytest.ini ai/tests -q`; `node --test frontend/tests/*.test.js`.
- [x] 격리 입력의 실제 Qwen 32개 회귀와 자유/제한 생성 비교를 단일 GPU 실행 주체가 수행한다. 핵심 3개 장소 성공, 근거 없는 hard 조건 저장0, 정상 완료 구조검증100%를 확인하고 false rejection/recall/p50/p95/잘림을 공개한다. 실패하면 계획 완료로 보고하지 않는다.
- [x] 기존 실제 방의 잘못된 조건은 자동 정정/삭제하지 않는다. 배포 후 별도 사용자 확인으로 정정하는 절차만 안내한다.
- [x] 문서에 모델·adapter 정책·정확한 의존성 버전·코드 버전·명령·결과·미검증 범위를 기록한다. 개인 스킬 체크 후 작은 커밋 목록을 정리한다.
- [x] 구현 요청에서 승인된 전달 범위와 브랜치 통합 경로를 확인한 뒤 develop push/master 대상 PR 절차를 따른다. 자동 merge하지 않는다. 계획 작성만으로 push/PR을 시작하지 않는다.

## 자체 검토 결과

- 형식/의미/실패·포인터/실제 모델 검증을 각각 Task2/3/5-6/7에 연결했다.
- optional conversation_context와 extraction_report는 기존 fixture 입력·출력과 공존한다.
- 의미 검증 거절의 포인터 전진, 형식 실패의 별도 보존, 실패 제외 후 새 메시지 선택, 수동 재처리 포인터 역행 방지를 명시했다.
- 사용자 미결정 사항은 권장 decoder 채택과 최종 구현 승인이다. 호환성/지연은 추정으로 통과 처리하지 않는다.


## 실행 결과

작업1–7과 독립 코드 리뷰의6개 수정 완료. 세부 구현 판단과 테스트 근거는 설계의 실제 적용 기록 및 docs/verification/grounded-qwen-extraction.md를 따른다. 전달은 사용자 지정 새 기능 브랜치에서 수행하며 develop/master에 직접 병합하지 않는다.

실제 구현의 내부 파싱은 `ExtractionBatch.model_validate()`를 직접 사용하며 별도 중복 파서 래퍼를 만들지 않았다. 조건 검증은 `project_condition()`의 수용/거절을 coordinator가 집계한다.

전달 완료: 새 기능 브랜치를 원격에 push하고 develop 대상 PR https://github.com/SEMI-CNU/trip-agent/pull/2 를 생성했다. 공유 develop/master에 직접 병합하지 않았다.
