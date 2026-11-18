# Vercel + Windows PC + Cloudflare Tunnel 운영 가이드

현재 기본 배포 방식은 도메인 구매가 필요 없는 [무료 ngrok](./vercel-ngrok.md)이다.
이 문서는 네임서버를 Cloudflare로 바꿀 수 있는 소유 도메인이 있을 때의 대안이다.
DuckDNS에서 받은 `semi-trip.duckdns.org`는 IP 갱신용 DDNS 주소이며, 일반 DuckDNS
계정에 Cloudflare로 네임서버를 위임하는 관리 기능이 제공된다고 안내할 근거가 없다.
따라서 DuckDNS 주소를 아래의 소유 도메인 대신 입력하는 절차로 진행하지 않는다.
[DuckDNS 제공 기능](https://www.duckdns.org/spec.jsp), [Cloudflare nameserver 조건](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)

Vercel은 정적 화면과 `/api/*` 중계를, Windows PC는 FastAPI·SQLite·GPU/Qwen을 맡는다.
연결은 `브라우저 → Vercel /api → 고정 Cloudflare Tunnel → 127.0.0.1:8000`이다.
PC의 outbound 연결을 사용하므로 공인 IP와 공유기 포트포워딩은 필요 없다.
이 문서는 배포 절차이며 실제 Cloudflare/Vercel 계정 설정과 공개 배포는 아직 수행하지 않았다.
아래 `example.com`과 `your-project.vercel.app`은 실제 접속할 도메인으로 바꾼다.

## 1. 준비와 비밀값의 위치

- 기존에 실제 AI가 동작하던 Windows PC, Python 3.12 Qwen 환경, 모델·어댑터·비공개 `.env`를 사용한다.
- Python 환경을 새로 만들거나 torch·모델을 다시 설치하지 않는다. 기존 모델 경로와 공급자 설정을 보존한다.
- Cloudflare 계정과 소유 도메인, Vercel 계정과 저장소 접근 권한을 준비한다.
- Cloudflare Free DNS 요금제를 선택할 수 있다. 도메인 등록·갱신 비용은 별도다.
- 서버 공급자 키, `DEV_TOKEN`, tunnel token, SQLite, 모델은 PC에만 둔다.
- Vercel에는 `BACKEND_ORIGIN`과 공개용 `KAKAO_JAVASCRIPT_KEY`만 설정한다.
  Kakao REST·Mobility 키, Apify 키, 서버 `.env` 전체를 옮기지 않는다.

공개 tunnel hostname은 직접 호출할 수도 있다. Vercel rewrite는 접근 제한 수단이 아니며,
백엔드의 로그인과 방 멤버 권한 검사가 계속 적용된다.

## 2. 기존 PC 백엔드 준비

기존 비공개 `.env`에 다음 운영 설정을 반영한다. 나머지 AI·공급자·DB 경로는 유지한다.

```dotenv
COOKIE_SECURE=1
SERVE_FRONTEND=0
PUBLIC_REQUESTS_PER_MINUTE=60
DEV_TOKEN=
TRACE_ENABLED=0
```

`DEV_TOKEN`을 비우면 공개 개발자 API를 비활성화한다. `TRACE_ENABLED=0`은 trace 저장을 끈다.
기존 shell 환경 변수가 `.env`보다 우선하므로 오래된 override도 제거하거나 같은 값으로 맞춘다.
아래는 저장소 루트에서 PowerShell로 실행한다. `$tripPython`은 실제 Qwen 환경 경로로 맞춘다.

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

`.env`가 다른 곳에 있다면 `TRIP_ENV_FILE`에 그 파일의 절대 경로를 지정한다.
Python 출력이 3.12인지, 기존 `AGENT_MODE`·`MODEL_BACKEND`·`PROVIDER_MODE`가 의도한 실제 AI 설정인지 확인한다.
`COOKIE_SECURE=1`은 공개 HTTPS용이다. 로컬 HTTP에서만 로그인 시험할 때는 별도 실행에서 `0`을 쓴다.
`SERVE_FRONTEND=0`은 PC의 프런트 작업 파일을 공개하지 않고 API만 제공한다.
PC 로컬 화면까지 사용할 때의 기본값은 `1`이며, 이 상태로 공개 tunnel을 운영하지 않는다.
한 PC에서 GPU 실행 서버는 하나만 띄우며 `--reload`나 여러 worker를 사용하지 않는다.

다른 PowerShell 창에서 DB 상태만 확인한다.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8000/api/health'
```

HTTP 200의 `{"status":"ok"}`는 DB 접근 가능을 뜻한다. 모델 준비·공급자 응답·여행안 품질 검사는 아니다.
DB를 사용할 수 없으면 HTTP 503을 반환한다. 먼저 로컬 health가 성공해야 다음으로 진행한다.

## 3. Cloudflare에 도메인 연결

1. Cloudflare에서 도메인을 추가하고 Free 요금제를 선택한다.
2. 기존 DNS 목록과 가져온 목록을 비교한다. 웹 A/AAAA/CNAME과 메일 MX, SPF·DKIM·DMARC·소유권 TXT를 보존한다.
3. 기존 DNSSEC가 켜져 있다면 공식 이전 절차에 따라 등록기관에서 먼저 끈다.
4. 도메인 등록기관의 nameserver를 Cloudflare가 지정한 두 주소로 바꾼다.
5. Cloudflare에서 도메인이 Active가 된 것을 확인한다. 기존 웹·메일이 정상인지 확인하고 DNSSEC를 다시 설정한다.

도메인을 Cloudflare에서 새로 구매했다면 nameserver 연결은 이미 되어 있을 수 있다.
기존 서비스의 DNS를 삭제해 빈 목록으로 만들지 않는다. [공식 도메인 연결 절차](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)

## 4. Windows에 고정 named tunnel 생성

1. Cloudflare 대시보드의 **Networking → Tunnels → Create Tunnel**에서 이름을 `trip-agent-pc`처럼 정한다.
   이전 화면에서는 **Zero Trust → Networks → Tunnels**로 표시될 수 있다.
2. 연결 방식으로 `cloudflared`와 PC의 Windows 아키텍처를 선택한다.
3. 화면의 Windows 설치 안내 또는 [공식 다운로드의 Windows MSI](https://developers.cloudflare.com/tunnel/downloads/)로 설치한다.
4. **관리자 PowerShell/명령 프롬프트**에서 대시보드가 제시한 서비스 설치 명령을 실행한다.

```powershell
cloudflared.exe service install <TUNNEL_TOKEN>
```

`<TUNNEL_TOKEN>`은 대시보드의 실제 값으로 PC에서만 바꾼다. 꺾쇠를 포함해 그대로 실행하지 않는다.
실행 파일이 PATH에 없다면 설치된 `cloudflared.exe`의 절대 경로로 실행한다.
토큰을 채팅·스크린샷·Git·Vercel 변수에 붙여넣지 않는다. 토큰 보유자는 connector를 실행할 수 있다.
유출되었다면 즉시 Rotate token 후 공식 문서의 **모든 기존 연결 강제 해제** 절차를 수행한다.
정상 PC 서비스도 새 토큰으로 재설치·재시작한다. Rotate만으로 기존 connector가 끊기지는 않는다.
[토큰 안내와 유출 대응 절차](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/)

5. tunnel이 **Healthy**가 되면 **Routes → Add route → Published application**을 추가한다.
6. hostname은 `api.example.com`, Service URL은 **`http://127.0.0.1:8000`**으로 지정한다.
   Service URL에 `/api`를 붙이지 않는다. 백엔드가 이미 `/api/*` 경로를 제공한다.
7. 연결된 DNS record와 Windows 서비스의 자동 시작 설정을 확인한다.
   기존 동일 이름 A/AAAA/CNAME이 있다면 다른 서비스 사용 여부를 확인하고 충돌을 해결한다.

서비스는 tunnel만 자동 실행한다. FastAPI는 별도로 실행 중이어야 한다.
Quick Tunnel의 임시 `trycloudflare.com` 주소는 SSE를 지원하지 않으므로 이 앱 배포에 사용하지 않는다.
[고정 tunnel 설정](https://developers.cloudflare.com/tunnel/get-started/), [Quick Tunnel 제한](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

## 5. Cloudflare API 캐시·인증 확인

도메인의 **Caching → Cache Rules → Create rule**에서 아래 조건에 **Bypass cache**를 설정한다.

```text
(http.host eq "api.example.com" and
 (http.request.uri.path eq "/api" or starts_with(http.request.uri.path, "/api/")))
```

겹치는 Cache Everything 규칙이 API를 다시 캐시하지 않도록 우선순위도 확인한다.
로그인·사용자별 JSON·SSE에 캐시를 적용하지 않는다. [공식 Cache Rules 절차](https://developers.cloudflare.com/cache/how-to/cache-rules/create-dashboard/)

API hostname에 브라우저 로그인을 요구하는 Cloudflare Access 페이지나 브라우저 challenge를 걸면
Vercel의 서버 중계와 EventSource가 HTML 인증 화면을 받아 실패할 수 있다.
이 구성은 앱의 로그인·방 권한 검사를 사용한다. 별도 Access를 추가하려면 서버 간 인증을 함께 설계해야 한다.
백엔드에 직접 접근해도 동일한 앱 인증이 필요하며 개발자 API는 비활성화한 상태를 유지한다.

```powershell
Invoke-RestMethod 'https://api.example.com/api/health'
```

로컬 health와 같은 JSON을 받아야 한다. tunnel Healthy 표시는 FastAPI/DB 정상까지 보장하지 않는다.

## 6. Vercel 정적 프런트엔드 배포

Vercel에서 저장소를 Import하고 다음 설정을 사용한다.

| 항목 | 값 |
| --- | --- |
| Root Directory | `frontend` |
| Production Branch | 현재 준비 코드가 있는 `develop` |
| Framework Preset | `Other` (`framework: null`) |
| Node.js Version | `24.x` |
| Build Command | 저장소 설정 `node scripts/build.mjs` 유지 |
| Output Directory | **Override를 끈다** |
| Install Command | 별도 의존성 설치 설정 불필요 |

이번 변경은 `develop`에 push되어 있으며 `master` 대상 PR은 아직 merge하지 않았다.
바로 배포할 때는 Production Branch/브랜치 추적을 `develop`으로 설정하고 해당 브랜치를
배포한다. 나중에 PR을 merge하고 운영 기준을 `master`로 옮길 때 이 설정도 맞춘다.

build는 `.vercel/output/static`과 `.vercel/output/config.json`을 만드는 Build Output API 방식이다.
Output Directory를 `dist`, `frontend` 또는 `.vercel/output/static`으로 덮어쓰지 않는다.
서버 실행용 `npm start`를 배포 명령으로 사용하지 않는다. [Build Output API](https://vercel.com/docs/build-output-api)

**Settings → Environment Variables**에서 설정하고 처음 배포한다.

| 변수 | 예시·범위 |
| --- | --- |
| `BACKEND_ORIGIN` | 필수: `https://api.example.com` |
| `KAKAO_JAVASCRIPT_KEY` | 선택: Kakao JavaScript 공개 키. 비우면 지도 대역 표시 |

`BACKEND_ORIGIN`에는 `/api`, 다른 경로, 계정정보, query, fragment를 붙이지 않는다.
실제 운영할 **Production** 범위에 설정하고, Preview도 시험할 경우 **Preview** 범위에 별도로 설정한다.
Preview가 같은 origin을 쓰면 같은 PC·DB·호출 예산에 연결된다.
변수는 build 때 적용되므로 변경 후 **Redeploy**한다. 기존 배포의 값은 자동 변경되지 않는다.
build는 키를 HTML에 escape해 넣고 API rewrite에 origin을 사용하며 서버 `.env`를 읽거나 복사하지 않는다.
정적 공개 파일은 HTML·CSS·`src`·`fixtures`로 제한된다.

브라우저 요청은 Vercel `/api/*`에 남아 있으므로 로그인 cookie와 SSE가 같은 origin을 사용한다.
Vercel의 API rewrite에는 캐시 비활성화가 적용된다. [외부 rewrite 캐시 제어](https://vercel.com/docs/routing/rewrites)

Kakao Developers의 **앱 → 플랫폼 키 → JavaScript 키 → JavaScript SDK 도메인**에
최종 **프런트엔드 origin**을 등록한다. [공식 지도 SDK 준비 안내](https://apis.map.kakao.com/web/guide/)
예: `https://your-project.vercel.app`. 지도 사용 예정 Preview/custom domain도 각각 등록한다.
API용 `https://api.example.com`만 등록해서는 화면의 SDK 요청을 허용할 수 없다.

## 7. PC 유지·재시작과 호출 제한

PC 절전·최대 절전·인터넷 단절·GPU 프로세스 종료 동안 API가 중단된다. 시연 중 절전을 끈다.
재부팅 자동 실행은 Windows 작업 스케줄러에서 기존 Python 실행 파일과 위 Uvicorn 인수를 사용하고,
**시작 위치를 저장소 루트**로, 비공개 `TRIP_ENV_FILE` 경로와 운영 환경 변수를 실행 wrapper에 지정한다.
기존 Qwen 환경을 읽을 수 있는 사용자로 실행하고 실패 시 재시작 설정을 확인한다.

worker와 GPU 실행 주체는 하나로 유지한다. SQLite의 계정·방·메시지는 같은 DB 경로 사용 시 남지만,
작업 queue와 provider 관측 메모리는 재시작 후 복구되지 않는다. 진행 중 AI 작업의 자동 재개를 기대하지 않는다.
정상 종료에도 GPU 작업이 정확히 5초 안에 취소됨을 보장하지 않는다.

`PUBLIC_REQUESTS_PER_MINUTE=60`은 단일 프로세스의 모든 API POST/PUT/PATCH/DELETE에 적용되는
전역 rolling 60초 예산이다. 로그인·가입도 예산을 소비하며 한 사용자가 모두 사용하면 다른 사용자도 429를 받는다.
429는 `Retry-After`를 확인하고 보통 60초 뒤 재시도한다. 연속 자동 재시도로 요청을 늘리지 않는다.
`0`은 제한 비활성화로 로컬 시험용이다. 이 제한은 사용자별 악용 방어나 GPU 처리량 보장이 아니다.

SSE는 즉시 comment와 이후 15초 heartbeat를 보낸다. Vercel은 첫 데이터 및 후속 데이터 간격이
120초를 넘으면 중계가 끊길 수 있다. 전체 스트림 길이가 2분으로 제한된 것은 아니다.
[Vercel 스트리밍 timeout 설명](https://vercel.com/changelog/cdn-origin-timeout-increased-to-two-minutes)

## 8. 공개 후 인수 확인과 장애 진단

자동 검증의 `https://api.example.com`은 가상 origin이며 실제 도메인이나 유료 공급자를 호출하지 않는다.
다음은 계정·도메인을 설정한 뒤 운영자가 수행할 실제 확인이다. AI 실행에는 기존 공급자 비용이 발생할 수 있다.

1. PC 로컬, tunnel hostname, 최종 Vercel의 `/api/health`가 모두 HTTP 200 JSON인지 확인한다.
2. Vercel에서 가입/로그인 후 새로고침해 로그인 유지, 로그아웃 후 세션 해제를 확인한다.
3. 서로 cookie를 공유하지 않는 브라우저 두 개에서 다른 계정으로 같은 방에 입장하고 대화를 주고받는다.
4. 개발자 도구 Network에서 `/events`가 `text/event-stream`으로 유지되는지 확인한다.
   2분 이상 아무 입력 없이 기다린 뒤 다른 브라우저의 새 메시지가 바로 보이는지 확인한다.
5. AI 작업 상태와 결과를 확인한다. `/api/health` 성공을 실제 Qwen·공급자 성공으로 대신 기록하지 않는다.
6. 정상 사용 중 429를 만나면 `Retry-After`와 전역 예산을 확인하고 60초 후 재시도한다.
7. 시험 시간을 정해 FastAPI를 중지하고 API 오류 표시를 확인한다. 같은 DB로 다시 켜서 health 복구,
   기존 계정·방 유지와 SSE 재연결을 확인하고 필요한 AI 작업만 다시 요청한다.

| 증상 | 우선 확인 |
| --- | --- |
| 502 / tunnel 오류 | PC·FastAPI 실행, 로컬 health, `127.0.0.1:8000` origin, tunnel 서비스/DNS 연결 |
| 504 / 장시간 정지 | 최초 응답 지연, SSE heartbeat/캐시/challenge, PC 절전과 GPU 상태 |
| 401 / 로그인 유지 안 됨 | 같은 Vercel origin 사용, HTTPS Secure cookie, cookie 전달·삭제, DB 경로 |
| 지도 대역 / SDK 실패 | Vercel 공개 키의 환경 범위, Redeploy 여부, 최종 프런트엔드 도메인 등록 |
| JSON 대신 HTML | Access 로그인·browser challenge, 잘못된 rewrite origin, Vercel 배포 보호 설정 |
| health 503 | SQLite 경로·권한·DB 연결; 모델/공급자 문제는 별도로 확인 |
