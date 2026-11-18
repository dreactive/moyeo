# Vercel + Windows PC + 무료 ngrok 운영 가이드

Vercel은 정적 화면과 `/api/*` 중계를, Windows PC는 FastAPI·SQLite·GPU/Qwen을 맡는다.
연결은 `브라우저 → Vercel /api → ngrok 고정 dev domain → 127.0.0.1:8000`이다.
도메인 구매, DuckDNS 연결, DNS·nameserver 변경, 공유기 포트포워딩은 필요 없다.
이 문서는 실행 절차다. 실제 설치·인증·ngrok 주소 발급·계정 설정·공개 배포는 아직 수행하지 않았다.

## 1. 기존 PC 환경과 비밀값 보존

- 실제 AI가 동작하던 Windows PC의 Python 3.12 Qwen 환경과 기존 모델·어댑터·비공개 `.env`를 사용한다.
- Python 환경·torch·모델을 다시 설치하지 않는다. 기존 AI 공급자·모델·DB 경로를 유지한다.
- 서버 공급자 키, `DEV_TOKEN`, ngrok authtoken, SQLite, 모델은 PC에만 둔다.
- Vercel에는 `BACKEND_ORIGIN`과 공개용 `KAKAO_JAVASCRIPT_KEY`만 설정한다.
  Kakao REST·Mobility 키, Apify 키, 서버 `.env` 전체를 복사하지 않는다.

ngrok 공개 주소는 누구나 직접 호출할 수 있다. Vercel rewrite는 접근 제한 수단이 아니며,
FastAPI의 로그인·방 멤버 권한 검사가 직접 요청에도 적용되어야 한다.
authtoken은 채팅·스크린샷·Git·Vercel 변수로 공유하지 않는다. 나중에 전달할 값은 공개 HTTPS 주소뿐이다.

## 2. FastAPI 실행과 로컬 확인

기존 비공개 `.env`에 아래 값을 반영하고 나머지 AI·공급자·DB 설정은 유지한다.

```dotenv
COOKIE_SECURE=1
SERVE_FRONTEND=0
PUBLIC_REQUESTS_PER_MINUTE=60
DEV_TOKEN=
TRACE_ENABLED=0
```

`DEV_TOKEN=`은 **환경 파일 자체에서** 비워 개발자 API를 끈다. shell에서 토큰만 지우는 것으로 대신하지 않는다.
shell·작업 스케줄러의 오래된 환경 변수는 `.env`보다 우선하므로 제거하거나 같은 값으로 맞춘다.
`SERVE_FRONTEND=0`은 PC의 프런트 작업 파일을 공개하지 않고 API만 제공한다. trace 저장도 끈다.
저장소 루트의 PowerShell에서 실행한다. `$tripPython`은 기존 Qwen 환경의 실제 Python 경로로 맞춘다.

```powershell
$tripPython = (Resolve-Path 'backend/.venv/Scripts/python.exe').Path
& $tripPython --version
$env:TRIP_ENV_FILE = (Resolve-Path '.env').Path
$env:COOKIE_SECURE = '1'
$env:SERVE_FRONTEND = '0'
$env:PUBLIC_REQUESTS_PER_MINUTE = '60'
$env:TRACE_ENABLED = '0'
Remove-Item Env:DEV_TOKEN -ErrorAction SilentlyContinue
& $tripPython -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1 --timeout-graceful-shutdown 5
```

`.env`가 다른 곳에 있다면 `TRIP_ENV_FILE`에 그 절대 경로를 지정한다. Python 3.12인지 확인한다.
기존 `AGENT_MODE`·`MODEL_BACKEND`·`PROVIDER_MODE`가 실제 AI 설정인지 확인하고 서버 창을 열어 둔다.
GPU 서버는 하나만 띄우며 `--reload`나 여러 worker를 사용하지 않는다.
`COOKIE_SECURE=1`은 공개 HTTPS용이다. 로컬 HTTP 로그인만 시험할 때는 별도 실행에서 `0`을 쓴다.

다른 PowerShell 창에서 먼저 로컬 health를 확인한다.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/health'
```

HTTP 200의 `{"status":"ok"}`는 DB 접근 가능을 뜻한다. 모델 준비·공급자 응답·여행안 품질 검사는 아니다.
DB 연결 실패는 HTTP 503이다. 로컬 health가 성공한 뒤 ngrok를 연결한다.

## 3. 무료 ngrok 계정·Windows 설치·주소 확인

1. [ngrok](https://ngrok.com/)에서 무료 계정을 만들고 로그인한다. 유료 플랜·자체 도메인은 필요 없다.
2. [공식 Windows 설치](https://ngrok.com/download/windows?tab=download)에 따라 Microsoft Store로 설치한다.
   PowerShell에서는 아래 공식 명령을 사용할 수 있다. 설치 후 새 터미널을 연다.

```powershell
winget install ngrok -s msstore
ngrok version
```

Store 사용이 불가능하면 같은 공식 페이지에서 PC 아키텍처에 맞는 실행 파일을 받는다.
실행 파일이 PATH에 없다면 `& '실제 절대 경로/ngrok.exe'` 형식으로 실행한다.

3. 대시보드 **Your Authtoken**의 값을 PC에서만 아래 placeholder 대신 넣는다.

```powershell
ngrok config add-authtoken "<본인_AUTHTOKEN>"
ngrok config check
```

이는 토큰을 로컬 ngrok 설정에 저장한다. 저장소에 설정 파일을 복사하지 않는다.
[공식 인증·CLI 안내](https://ngrok.com/docs/gateway/agent/cli)

4. FastAPI가 실행 중인 상태에서 새 창에 다음 명령을 실행하고 **이 창도 열어 둔다**.

```powershell
ngrok http http://127.0.0.1:8000
```

5. 출력의 **Forwarding**에서 HTTPS 주소를 확인한다. 대시보드 **Domains**에서도 볼 수 있다.
   무료 계정의 dev domain은 재시작해도 유지된다. `.ngrok-free.dev` 또는 `.ngrok-free.app`일 수 있다.
   화면에 배정된 주소를 정확히 사용하며 `semi-trip.duckdns.org`를 연결하거나 대신 입력하지 않는다.
6. 필요하면 배정 주소를 명시할 수 있다. 무료 플랜에서 임의 이름을 선택하는 옵션은 아니다.

```powershell
ngrok http http://127.0.0.1:8000 --url https://본인에게-배정된-주소.ngrok-free.dev
```

두 ngrok 명령을 동시에 실행하지 않는다. 하나를 중지한 뒤 다른 형태를 사용한다.
[공식 시작 절차](https://ngrok.com/docs/gateway/endpoints/agent-cli-quickstart), [고정 dev domain](https://ngrok.com/docs/gateway/domains)

ngrok 창은 열어 두고 **별도 PowerShell**에 실제 배정된 origin을 넣어 공개 경로를 확인한다.

```powershell
$tripNgrokOrigin = 'https://본인에게-배정된-주소.ngrok-free.dev'
Invoke-RestMethod "$tripNgrokOrigin/api/health" -Headers @{ 'ngrok-skip-browser-warning' = '1' }
```

로컬과 같은 JSON을 받아야 한다. ngrok가 online이어도 FastAPI·DB 정상까지 보장하지 않는다.

## 4. 기존 Vercel 프로젝트 설정·재배포

기존 프로젝트의 설정을 확인한다. 처음 연결하는 경우 저장소를 Import하고 동일한 값을 사용한다.

| 항목 | 값 |
| --- | --- |
| Root Directory | `frontend` |
| Production Branch | 현재 준비 코드가 있는 `develop` |
| Framework Preset | `Other` (`framework: null`) |
| Node.js Version | `24.x` |
| Build Command | 저장소 설정 `node scripts/build.mjs` 유지 |
| Output Directory | **Override를 끈다** |
| Install Command | 별도 의존성 설치 설정 불필요 |

build는 Build Output API의 `.vercel/output/static`과 `.vercel/output/config.json`을 만든다.
Output Directory를 `dist`나 `.vercel/output/static`으로 덮어쓰거나 `npm start`를 실행하지 않는다.
나중에 운영 브랜치를 `master`로 옮기면 Production Branch도 맞춘다. [Build Output API](https://vercel.com/docs/build-output-api)

**Settings → Environment Variables**를 아래 값으로 변경한다.

| 변수 | 값 |
| --- | --- |
| `BACKEND_ORIGIN` | 실제 배정된 `https://…ngrok-free.dev` 또는 `https://…ngrok-free.app` |
| `KAKAO_JAVASCRIPT_KEY` | 선택: Kakao JavaScript 공개 키. 비우면 지도 대역 표시 |

`BACKEND_ORIGIN`에는 `/api`, 다른 경로, 계정정보, query, fragment를 붙이지 않는다.
**Production** 범위에 설정하고 Preview도 쓸 경우 **Preview** 범위에도 설정한다.
Preview가 같은 origin을 쓰면 같은 PC·DB·호출 예산에 연결된다.
Deployments에서 이번 ngrok 설정 변경이 포함된 최신 `develop` 배포를 선택해 **Redeploy**한다.
이전 커밋의 배포를 다시 실행하는 대신 새 코드가 반영됐는지도 확인한다.
build 변수 변경은 기존 배포에 자동 적용되지 않는다.
Kakao Developers의 JavaScript SDK 도메인에는 최종 **Vercel 프런트엔드 origin**을 등록한다.
예: `https://your-project.vercel.app`. 지도 사용 예정 Preview·custom domain도 등록한다.
ngrok 주소만 등록해서는 프런트 지도 SDK를 허용할 수 없다. [Kakao 지도 준비 안내](https://apis.map.kakao.com/web/guide/)

## 5. 중계·cookie·SSE 동작

브라우저는 Vercel `/api/*`에 요청한다. 중계는 ngrok의 `/api/*`로 경로를 유지하므로 cookie와 SSE는 같은 origin이다.
build가 만드는 API 중계는 ngrok로 보내는 **요청 header**에 `ngrok-skip-browser-warning: 1`을 추가한다.
브라우저 fetch와 EventSource 모두 이 경로를 사용한다. 프런트 요청·cookie 코드를 별도로 바꿀 필요는 없다.
이는 응답 header가 아니며 ngrok Traffic Policy의 add-headers 설정도 아니다.
API 중계의 캐시는 꺼져 있다. 로그인·사용자별 JSON·SSE에 캐시를 추가하지 않는다.
[ngrok 경고 화면·요청 header](https://ngrok.com/docs/pricing-limits/free-plan-limits), [Vercel 외부 rewrite](https://vercel.com/docs/routing/rewrites)

무료 ngrok는 HTML 브라우저 트래픽에 경고 화면을 표시한다. API·프로그램 접근은 별도로 안내되지만,
실제 배포에서는 JSON·`text/event-stream`이 HTML로 바뀌지 않는지 확인한다.
SSE는 즉시 comment와 15초 heartbeat를 보낸다. Vercel은 최초 데이터와 후속 데이터 사이가 120초를 넘으면 끊길 수 있다.
전체 스트림이 2분으로 제한되지는 않는다. [Vercel timeout](https://vercel.com/changelog/cdn-origin-timeout-increased-to-two-minutes)

## 6. 무료 한도와 PC 유지

무료 플랜은 월 outbound **1GB**, HTTP 요청 **20,000회**, online endpoints **3개**가 한도다.
ngrok endpoint 실행시간·전체 HTTP 왕복시간의 고정 상한은 없지만, 무응답 연결의 idle timeout은 **5분**이다.
heartbeat를 유지하고 대시보드 Usage를 확인한다. 이 숫자는 동시 사용자 수나 사용 가능 일수 보장이 아니다.
[무료 한도](https://ngrok.com/docs/pricing-limits/free-plan-limits), [연결 timeout](https://ngrok.com/docs/gateway/endpoints/http)

PC 절전·최대 절전·재부팅·인터넷 단절·FastAPI/ngrok 종료 동안 API가 중단된다. 시연 중 절전을 끈다.
자동 시작을 구성한다면 기존 Qwen 환경을 읽는 사용자와 저장소 시작 위치·`TRIP_ENV_FILE`을 유지한다.
GPU worker는 하나로 둔다. 같은 SQLite 경로의 계정·방·메시지는 남지만 작업 queue·관측 메모리는 재시작 후 복구되지 않는다.
진행 중 AI 작업은 자동 재개되지 않으며 정상 종료의 5초 옵션도 GPU 취소 완료를 보장하지 않는다.
`PUBLIC_REQUESTS_PER_MINUTE=60`은 모든 API 쓰기 요청의 전역 rolling 60초 예산이다. 가입·로그인도 소비한다.
한 사용자가 예산을 쓰면 다른 사용자도 429를 받을 수 있다. `Retry-After`를 따르고 연속 자동 재시도를 피한다.

## 7. 공개 후 확인과 장애 진단

1. PC 로컬, ngrok 공개 주소, 최종 Vercel의 `/api/health`가 모두 HTTP 200 JSON인지 확인한다.
2. Vercel에서 가입·로그인 후 새로고침 유지, 로그아웃 후 세션 해제를 확인한다.
3. cookie를 공유하지 않는 브라우저 두 개에서 다른 계정으로 같은 방에 들어가 메시지를 주고받는다.
4. Network의 `/events`가 `text/event-stream`인지 확인한다. **2분 이상 입력 없이** 기다린 뒤 새 메시지가 바로 보이는지 확인한다.
5. 실제 AI 실행은 필요할 때 별도로 확인한다. 기존 유료 공급자 비용이 발생할 수 있으며 health 성공으로 대신 검증하지 않는다.
6. FastAPI를 중지·재시작해 오류 표시, 같은 DB의 기존 계정·방 유지, SSE 재연결을 확인한다.

| 증상 | 우선 확인 |
| --- | --- |
| ngrok offline / 502 | FastAPI·ngrok 창, 로컬 health, `127.0.0.1:8000`, 실제 배정 주소 |
| JSON 대신 HTML | 새 중계 코드 Redeploy 여부, ngrok 요청 header, Vercel 배포 보호 |
| 401 / 로그인 유지 실패 | 같은 Vercel origin, HTTPS Secure cookie, DB 경로 |
| SSE 정지 | 15초 heartbeat, `text/event-stream`, 캐시, PC 절전·네트워크 |
| 429 / ngrok 한도 오류 | 앱 `Retry-After`와 전역 예산, ngrok Usage·오류 코드 구분 |
| 지도 대역 / SDK 실패 | 공개 키 환경 범위·Redeploy, 최종 프런트엔드 SDK 도메인 |
| health 503 | SQLite 경로·권한·DB 연결; 모델·공급자 상태는 별도 확인 |
