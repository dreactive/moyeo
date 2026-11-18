# 공동 여행 계획 웹 서비스

2026-11-17 서비스 기획과 2026-11-18 확정한 구현 범위를 기준으로 작업한다.

**기준 문서: [서비스 기획서 v1.0](./docs/travel-agent-service-plan.md)**

**최신 구현 기준: [MVP 설계](./docs/superpowers/specs/2026-11-18-travel-agent-design.md) · [공통 API 계약](./docs/contracts/travel-api.md)**

구현 세부가 기존 기획과 다르면 2026-11-18 설계를 따른다. 구현과 실제 검증 범위는 [Backend 기록](./docs/verification/backend.md), [FE 기록](./docs/verification/frontend.md), [AI 기록](./docs/verification/ai.md), [통합 기록](./docs/verification/integration.md)에서 구분한다. fixture/fake 통과를 실제 API·Qwen 완료로 보지 않는다.

- 계정과 참가 코드로 입장하는 자체 웹 단체 채팅방.
- 왼쪽 채팅 약 30%, 오른쪽 여행 조건·전체 동선·선택 장소·예상 경비 약 70%.
- 에이전트는 오른쪽에서 조사·계산·제안하고 사람 채팅에는 참여하지 않는다.
- 같은 여행안 버전에 참가자 전원이 동의한 뒤 확정한다.
- 항목 언급은 빨강, 과반의 명시적 대화 지지는 노랑, 여행안 전체를 전원이 확인하면 포함 항목은 초록이다. 충돌은 별도 느낌표로 표시한다.
- 국내·자동차 여행부터 구현하며, 대표 데모는 여수 4명 1박 2일이다.
- SABench, When2Call, 여행 전용 평가와 실제 그룹 사용 실험을 구분한다.

[보조 설계 자료](./docs/travel_service_plan.md)는 같은 서비스의 참고 문서이며, 변경 판단은 기준 문서를 따른다.

[대회 핵심 요구사항](./docs/hackathon-key-requirements.md)은 대회 안내 PDF를 재독한 요약이다. 2026년 모델·평가·제출 기준과 2025년 참고 자료를 구분하고 원문 페이지를 연결한다.

## 개발·검증 문서

세 세션은 [병렬 구현 총괄](./docs/superpowers/plans/2026-11-18-three-session-plan.md)을 먼저 읽는다. S1은 FE, S2는 BE·최종 통합, S3는 AI를 소유하며 각자 테스트 대역으로 상대 구현 없이 시작한다.

| 문서 | 용도 |
|---|---|
| [S1 FE 개발 계획](./docs/superpowers/plans/2026-11-18-frontend.md) | frontend/ 독점, Backend 없는 fixture 화면 개발 |
| [S2 BE 개발 계획](./docs/superpowers/plans/2026-11-18-backend.md) | backend/ 독점, 가짜 Agent로 API·상태·동의·통합 |
| [S3 AI 개발 계획](./docs/superpowers/plans/2026-11-18-ai.md) | ai/ 독점, BE 없는 JSON 재생·모델·도구·계산 |
| [동결 JSON 예제](./docs/contracts/examples/README.md) | 세 세션의 입력·출력·테스트 대역 기준 |
| [기능 검증 체크리스트](./docs/testing/mvp-checklist.md) | 기능별 완료 기준과 실행 증거 기록 |
| [가격·영업시간 공급자 설계](./docs/providers/place-data.md) | Apify 검증과 무료 API 전환, 실제 데이터 확인 기준 |

코드는 frontend/, backend/, ai/로 나누고 docs/ 등은 공용으로 둔다. 기존 submission/과 원문 PDF는 보존한다.

`docs/`의 대회 안내 PDF와 `data/`의 기존 원본 자료는 보존한다. 원본 자료의 존재가 현재 서비스의 구현 범위를 정의하지는 않는다.

## 실행

Vercel 화면과 개인 Windows PC 서버를 연결하려면
[무료 ngrok 배포 가이드](./docs/deployment/vercel-ngrok.md)를 따른다.
`frontend/vercel.json`은 `BACKEND_ORIGIN`과 공개 지도 키로 정적 배포 산출물을 생성한다.
도메인 구매 없이 ngrok 계정의 무료 고정 주소를 사용한다. 계정·토큰·실제 배포 설정과
공개 후 확인은 가이드의 별도 단계다. 소유 도메인이 있다면
[Cloudflare Tunnel 대안](./docs/deployment/vercel-cloudflare.md)도 사용할 수 있다.

저장소 루트에서 실행한다. Windows의 `python` 별칭이 실행되지 않으면 설치된 Python 실행 파일의 절대 경로를 사용한다. 로컬 Qwen 통합 환경은 Python 3.12를 사용했다.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

[사용자 화면](http://127.0.0.1:8000/)과 [개발자 화면](http://127.0.0.1:8000/dev)은 같은 origin에서 API·cookie·방 SSE를 사용한다. frontend가 없어도 Backend API는 실행된다. 기본 `AGENT_MODE=fixture`는 고정 Backend 예제이며 임의 대화를 이해하는 모델이 아니다. FE만의 정해진 화면 시나리오는 [fixture 화면](http://127.0.0.1:8000/?mode=fixture)으로 연다. 이때 HTTP 인증·실제 모델·실제 장소 조회를 검증한 것으로 보지 않는다.

AI 연결은 독립 테스트 이후 별도로 설정한다. [AI 실행 안내](./ai/README.md)의 의존성을 같은 통합 환경에 설치하고, 먼저 `MODEL_BACKEND=fake`, `PROVIDER_MODE=fixture`를 사용한다.

```powershell
backend/.venv/Scripts/python.exe -m pip install -r ai/requirements.txt
$env:TRIP_ENV_FILE=(Resolve-Path .env).Path
$env:AGENT_MODE='local_ai'
$env:MODEL_BACKEND='fake'
$env:PROVIDER_MODE='fixture'
backend/.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

실제 Qwen은 Python 3.12 통합 환경에 선택 의존성을 설치하고 로컬 모델 경로를 지정한다. 아래 베이스 경로는 실제 준비한 디렉터리로 바꾼다. 모델을 자동 다운로드하지 않는다.

```powershell
backend/.venv/Scripts/python.exe -m pip install -r ai/requirements-local-qwen.txt
$env:BASE_MODEL_PATH='C:/path/to/Qwen2.5-1.5B-Instruct'
$env:ADAPTER_PATH=(Resolve-Path submission/weights).Path
$env:MODEL_BACKEND='local_qwen'
$env:PROVIDER_MODE='live'
backend/.venv/Scripts/python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --timeout-graceful-shutdown 5
```

이 명령은 앞 단계의 `TRIP_ENV_FILE`과 `AGENT_MODE=local_ai`를 유지한다. 실제 공급자는 AI 안내의 공급자 설정·키가 필요하다. 서버를 한 프로세스·worker 하나로 실행하고 GPU 실행은 한 세션만 맡는다. 모델·공급자 오류를 fixture 성공으로 자동 대체하지 않는다.

현재 실모델 지연은 큰 제한이다. RTX4070 환경에서 실제 AI 단독 5도구 실행은 약 9분50초, 기존 일정에서 조건 추가·충돌 선택·재확정까지의 4인 통합은 약 28분39초였다. 모델 판단 후보의 전체 경로 인자는 유지되며 성능 최적화는 남아 있다. 자유 문장 추출에는 근거 메시지를 보존한 규칙 보조가 포함되고, 지역명만으로 전체 일정을 발견·완성하지는 않는다. 관측된 가격·시간과 사용자 입력·미확인 값은 구분한다.

`.env`는 Git 제외 파일이다. `TRIP_ENV_FILE`로 다른 작업 공간에서도 같은 절대 경로를 지정할 수 있고 shell 환경 변수가 파일 값보다 우선한다. `KAKAO_JAVASCRIPT_KEY`만 공개 지도 키로 HTML에 주입한다. 실제 서비스 origin을 Kakao SDK 도메인에 등록한다. REST·Mobility·Apify 키와 `DEV_TOKEN`은 브라우저 코드에 넣지 않는다. 개발자 trace는 로그인한 방 멤버의 cookie와 `X-Dev-Token`이 모두 필요하며, 토큰은 로컬 `.env`에서 확인한다. `TRACE_ENABLED=0`이어도 장소·근거 데이터는 trace와 별도로 유지된다.

## 검증

```powershell
node --test frontend/tests/*.test.js
backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q
backend/.venv/Scripts/python.exe -m pytest -c ai/pytest.ini ai/tests -q
backend/.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q -m integration
```

Backend 기본 테스트는 integration marker를 제외하고 AI 패키지를 import하지 않는다. AI 실제 모델·공급자 probe와 4인 통합의 실행 상태·코드 버전·남은 제약은 통합 기록과 C01–C47 검증표를 따른다. 관측·진단 로그와 SQLite·가상환경은 Git에 넣지 않는다.
