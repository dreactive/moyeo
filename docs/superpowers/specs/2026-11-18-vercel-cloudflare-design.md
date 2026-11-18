# Vercel + 개인 PC 공개 배포 설계

사용자가 2026-11-18 대화에서 선택하고 구현을 요청한 구성이다.
Vercel은 정적 화면과 같은 origin의 `/api/*` 중계를 맡고, Windows PC의
FastAPI 한 worker가 SQLite와 로컬 Qwen을 계속 소유한다.
Cloudflare의 고정 published application을 `http://127.0.0.1:8000`에 연결한다.

## 접근 방식

- 선택: Vercel → 고정 Cloudflare Tunnel → PC. 현재 상대 API 경로와 host-only
  로그인 cookie를 유지하고 공유기 inbound 포트를 열지 않는다.
- 직접 API origin 호출은 CORS·cross-site cookie 변경이 필요해 선택하지 않았다.
- 포트포워딩은 공개 IP·HTTPS·공유기 설정 관리가 필요해 선택하지 않았다.

## 구현 범위

- SSE는 연결 즉시 comment를 보내고 이후 15초 간격으로 heartbeat를 보낸다.
  comment에는 event ID를 넣지 않아 Last-Event-ID 재생 계약을 유지한다.
- `COOKIE_SECURE=1` 배포 설정으로 HTTPS cookie를 쓰며 로컬 HTTP 기본값은 유지한다.
- 모든 `/api` 응답은 `Cache-Control: no-store`이고 상태 확인용 `/api/health`는
  DB 연결 가능 여부만 확인한다. 모델 품질·공급자 성공을 뜻하지 않는다.
- API의 공개 POST/PATCH/DELETE 요청에는 같은 프로세스의 전역 분당 제한을 둔다.
  기본 60회이며 초과는 상태 변경 전에 429와 Retry-After를 반환한다.
  이는 GPU 처리량 보장이 아니며 봇·악용 방어를 대체하지 않는다.
- Vercel Build Output API로 backend origin과 정적 파일을 생성한다.
  `BACKEND_ORIGIN`은 경로·인증정보 없는 HTTPS origin만 허용한다.
  `KAKAO_JAVASCRIPT_KEY`만 HTML에 escape해서 삽입한다.
  배포 파일은 index/dev HTML, CSS, src, fixtures로 제한한다.
- Vercel 환경 변수나 산출물에 서버 .env, 모델, SQLite, token을 넣지 않는다.
- 공개 API origin도 로그인·권한 검사를 유지한다. 운영 가이드에 API 캐시 제외,
  개발자 token 비활성화, 터널 token 보관, DNS·Kakao 등록, Windows 자동 실행과
  로그인/방/SSE/AI/장애복구 확인 순서를 제공한다.

## 범위와 완료 기준

외부 계정 생성, 도메인 구매, 실제 Cloudflare/Vercel 배포와 유료 live API 호출은
수행하지 않는다. 사용자가 도메인을 설정하고 환경 변수를 입력해야 실제 공개된다.
현재 AI 추론 지연과 단일 PC 가용성은 유지되는 제약이다.
기존 API·FE 테스트, 새로운 HTTP/스트림 동작 테스트와 정적 배포 산출물 검증을 통과한다.
개인 AGENTS.md·skill과 기존 미추적 문서는 변경하거나 커밋하지 않는다.
