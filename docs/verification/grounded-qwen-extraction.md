# 로컬 Qwen 스키마·근거 기반 추출 검증 — 2026-11-18

브랜치: `codex/grounded-qwen-extraction`. 기능 기준: `19d3b94` (이후 커밋은 결과/계약 문서). 시작점은 후보 생성 전용 `718ede7`이다.

로컬 Qwen을 그대로 사용하며 모델이 메시지별 작은 `MessageFacts`를 생성한다. Pydantic/JSON Schema 토큰 제한 후 코드가 발화자·원문 근거를 붙이고 조건 의미를 검사한다. 모델 단독 정답률과 전체 파이프라인 결과를 구분한다. 생성 시 judge adapter는 기존처럼 비활성화하며 채점·선택·자동 도구 실행·새 일정 생성은 하지 않는다.

## 실행 환경

- NVIDIA GeForce RTX4070, VRAM12282MiB.
- 기존 로컬 Qwen2.5-1.5B-Instruct 베이스와 제공된 adapter 파일. 자동 모델 다운로드 없음.
- Python3.12, Torch2.14.1+cu126, Transformers4.57.6, PEFT0.21.3, Pydantic2.14.3, LM Format Enforcer0.11.3.
- 전용 `.data/extraction-venv`를 사용했다. 기존 설치된 ML 패키지를 읽기 전용으로 참조하며 새 의존성은 전용 환경에 설치했다.
- 실제 사용자 방·기존 DB·서버 설정은 검증 대상으로 변경하지 않았다. 입력은 익명화한 별도 사례, 공급자는 fixture다. 실제 Kakao/가격/영업시간 데이터 품질 검증은 아니다.

## 자동 회귀

| 검증 | 결과 |
|---|---|
| AI 전체 |179 passed |
| Backend 기본 |120 passed, integration3 deselected |
| Backend 통합 |3 passed |
| Frontend |40 passed |

Backend에는 기존 Starlette/httpx deprecation 경고1개가 있다. 본 변경의 실패가 아니다. 기존 통합 테스트3개는 과거 자동 도구 실행/일정 생성을 기대했으므로, 현 후보 생성 전용 계약에 맞춰 후보·기존 계획/근거 보존·공동 지지·개인 조건 소유권을 검증하도록 바꿨다.

## 실제 Qwen32개 비교

고정 사례는 `ai/eval/extraction_cases.jsonl`의 장소8/조건8/지지8/무정보·부정8개다. 모든 사례는 각자 독립 입력/상태를 사용한다. 한 모델 인스턴스를 재사용하고 warmup을 제외했다. 제한/자유 생성 모두 동일한 작은 스키마 프롬프트와 동일한 근거 검증을 사용한다. 따라서 이 비교는 과거 큰 프롬프트 구현 전체의 전후 성능 비교가 아니다.

| 지표 | 스키마 제한 생성 | 자유 생성 비교 |
|---|---:|---:|
| 파이프라인 기대값 일치 |32/32 |32/32 |
| 전남대학교/롤링 파스타/오동도 핵심3개 |3/3 |3/3 |
| 조건 값 불일치/근거·소유권 오류 |0/0 |0/0 |
| 스키마 실패 |0 |0 |
| 자동 도구 호출 |0 |0 |
| warm p50 |0.521초 |0.407초 |
| warm p95 |0.910초 |0.596초 |

p95 비율은 약1.53배로 설계의2배 검토 기준 이내다. 작은 고정 표본의 수치이며 모든 한국어 문장이나 운영 지연을 보장하지 않는다. 입력별 출력 토큰 수, 호출 수, 오류 코드와 지연은 로컬 보고서에 보존했다.

**두 조건 사례는 모델 단독 정답이 아니다.** `내 예산은2.5만원`과 `오전12시까지 귀가해야 해`의 모델 정규화 값은 거절했고, 완전한 원문 문장으로 확인한25000원/00:00만 규칙 보조로 반영했다. `condition_rule_assisted`로 구분한다. 인사/점심/부정/타인 발언에는 이 보조가 값을 만들어 넣지 않는다.

## 실제 출력의 SQLite 반영 검사

최종32개 실제 모델 출력을 별도 SQLite에 재생했고, 이후 실제 모델로 추가10개 작업을 실행하여 총42개 격리 방을 확인했다.

- 예기치 않은 조건 저장0건. 저장한 개인 조건은 모두 실제 작성자의 값이며 `needs_owner_confirmation` 상태다.
- 새 일정 생성0건, 자동 공급자 도구 실행0건.
- 추가6개 조건 경계: 불확실한 예산/전언/동생의 귀가/예산 아닌 선물 금액/복수 예산은 임의 hard 조건으로 저장되지 않았다. `200,000원`은 정확히200000원으로 처리했다.
- 실제 `new_message`3회에서 전남대학교/롤링 파스타/오동도의 후보가 각각3/2/2개 생성되었다. 도구 실행은 없었다.
- 두 참가자가 같은 배치에서 `오동도 가자`를 보낸 실제 모델 실행은 장소1개, 작성자별 지지2개와 근거2개로 반영되었다.

로컬 증거는 `.planning/grounded-qwen/live-report-reviewed.json`, `reviewed-sqlite-audit.json`, `reviewed-output-audit.sqlite3`에 남겼다. 원시 모델 진단 출력/관측 로그/SQLite/가상환경은 Git에 추가하지 않는다. 다른 개발자는 아래 CLI와 Backend 회귀로 동일한 입력·반영 경계를 재검증할 수 있다.

## 독립 코드 리뷰와 수정

`129836e`에 대한 독립 읽기 전용 리뷰에서 발견한6개 문제를 각각 재현 테스트의 RED→GREEN으로 수정했다. 수정 후 전체 회귀와 실제 모델/SQLite 검사를 다시 수행했다. 리뷰어는 GPU 결과 자체를 독립 재검증한 것은 아니다. 보류한 minor는 없다.

1. 완전한 자기 조건 문장과 전체 숫자를 검사하여 불확실/전언/타인 조건 및 쉼표 금액 오류 차단.
2. 코드가 붙이는 원문 근거 상한을 API 입력과 동일하게10000자로 정렬.
3. 비어 버린 대기 작업이 앞선 needs_input/거절 상태를 지우지 않도록 보존.
4. 같은 정규화 장소명은 모든 원문 ID를 합친 뒤 지지를 계산.
5. 선택 맥락은 남은 토큰 예산과2000토큰 상한 안에만 추가하고 현재 메시지를 보존.
6. JSON이 닫혀 있어도 EOS 없이 토큰 한도에서 중단된 추출은 실패 처리.

## 재검증 명령

저장소 루트에서 필요한 의존성을 설치한 Python을 사용한다. 로컬 경로는 실제 준비한 가중치로 바꾼다.

```powershell
python -m pytest -c ai/pytest.ini ai/tests -q
python -m pytest -c backend/pytest.ini backend/tests -q
python -m pytest -c backend/pytest.ini backend/tests -q -m integration
node --test frontend/tests/*.test.js
python -m ai.eval.extraction_replay --model-backend local_qwen --base-model-path C:/path/to/Qwen2.5-1.5B-Instruct --adapter-path submission/weights --compare-unconstrained --output .planning/extraction-report.json
```

## 남은 범위와 운영 반영

- 일반 고유명사/지역/활동 분류에는 모델 오류 가능성이 남는다. 원문에 없는 이름·지점은 거절하지만, 모든 도시나 사람 이름의 의미 분류를 보장하는 지명 사전/NER 시스템은 아니다.
- 현재 자동 확인 가능한 조건은 개인 예산과 귀가 마감이다. 지원하지 않는 key와 불명확한 문법/복수 값은 needs_input으로 남기며 표현을 명확히 하거나 별도 validator를 추가해야 한다.
- 기존 DB에 저장된 잘못된 조건은 자동 삭제·역추적 수정하지 않았다. 기존 실행 서버는 새 브랜치/의존성으로 재시작한 뒤 새 메시지부터 동작을 확인해야 한다.
- 본 기능 브랜치를 전달하며 develop/master에 직접 병합하거나 기존 열린PR#1을 자동 병합하지 않는다.
