# Vercel + 무료 ngrok 배포 설계

사용자가 도메인 구매 없이 ngrok 무료 플랜으로 전환하고 기존 Vercel 설정을
맞추도록 2026-11-18 명시적으로 요청했다. 기존 PC 실행과 로그인·SSE는 유지한다.

## 선택과 범위

- 선택: 브라우저 → Vercel `/api/*` → 계정에 자동 배정된 고정 ngrok HTTPS 주소
  → PC `127.0.0.1:8000`. DuckDNS나 별도 DNS 변경은 필요하지 않다.
- 기존 Cloudflare 구성은 소유 도메인이 있을 때의 대안으로 남긴다.
  DuckDNS DDNS 주소는 Cloudflare nameserver 위임을 제공하는 소유 도메인과 다르다.
- Vercel Build Output API의 API route에 `request.headers` transform으로
  `ngrok-skip-browser-warning: 1`을 설정한다. 응답용 headers와 구분한다.
  EventSource는 임의 요청 헤더를 넣을 수 없으므로 fetch만 수정하지 않는다.
- `BACKEND_ORIGIN`은 실제 할당된 HTTPS origin을 입력하며 `/api`를 붙이지 않는다.
  공개 Kakao 키만 HTML에 넣고 기존 정적 allowlist와 no-store를 유지한다.
- PC의 COOKIE_SECURE=1, SERVE_FRONTEND=0, 단일 worker, SSE 15초 heartbeat는 유지한다.
- 기본 진입 안내와 환경 변수 예제를 ngrok로 바꾸고 설치·토큰·고정 주소·Vercel
  Redeploy·Kakao SDK 도메인·실제 인수 확인과 무료 한도를 문서화한다.

## 완료 기준

기존 FE 회귀와 실제 정적 build가 통과하고, 생성한 `/api` route가 요청 transform과
기존 경로/캐시 설정을 함께 포함한다. 독립 검토 후 작은 커밋·develop push·PR 갱신한다.
사용자 계정·설치·authtoken·실제 ngrok 주소는 제공받지 않았으므로 계정 조작이나
실제 배포를 완료했다고 주장하지 않는다. ngrok 설치·토큰 등록·실제 할당 주소 입력과
공개 HTTPS cookie/SSE 확인은 사용자가 가이드대로 수행해야 한다.
