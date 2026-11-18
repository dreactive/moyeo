# 무료 ngrok 배포 준비 검증

2026-11-18, 이전 배포 준비 `b033580`에서 사용자가 ngrok 무료 플랜 전환을 선택했다.

## 변경과 근거

- 기존 `/api/*` 외부 route에 `request.headers` transform을 추가해
  `ngrok-skip-browser-warning: 1`을 ngrok으로 전달한다.
- 응답용 no-store/cache opt-out headers와 구분하며 fetch·EventSource 모두 같은 경로에 적용된다.
- `BACKEND_ORIGIN` 예제를 무료 할당 `.ngrok-free.dev` origin으로 바꿨다.
  실제 할당 주소가 `.ngrok-free.app`이어도 기존 HTTPS origin 검증이 허용한다.
- PC의 cookie·API 전용 실행·SSE heartbeat·backend/AI 런타임은 변경하지 않았다.
- README/FE/API 계약에서 기본 안내를 ngrok로 연결했다. 기존 Cloudflare 가이드는
  네임서버 관리가 가능한 소유 도메인용 대안으로 남기고 DuckDNS 제약을 명시했다.

공식 근거:
[Vercel 요청 transform](https://vercel.com/docs/build-output-api/configuration),
[외부 origin 요청 헤더 예제](https://vercel.com/changelog/transform-rules-are-now-available-in-vercel-json),
[ngrok 무료 경고·한도](https://ngrok.com/docs/pricing-limits/free-plan-limits),
[고정 할당 주소](https://ngrok.com/docs/gateway/domains).

## 검증 결과

- `node --test frontend/tests/*.test.js`: **45 passed**.
- Node 24 실제 build CLI: `.vercel/output/config.json` v3 생성.
- 가상 `.ngrok-free.dev` origin으로 로그인·SSE 경로의 `/api` prefix 유지 확인.
- 생성된 API route의 **요청** 헤더 transform이 bypass 값 1을 설정함을 확인.
- 기존 API no-store 유지, 정적 파일 5종 allowlist, 공개 지도 키 삽입을 확인.
- 비밀값 sentinel이 config에 포함되지 않음을 확인. 실제 authtoken은 읽거나 요청하지 않았다.
- 변경은 선언적 라우팅 설정이므로 구현을 복제하는 테스트는 추가하지 않고 기존 회귀와
  실제 빌드 산출물을 공식 스키마에 맞춰 확인했다. backend/AI는 변경하지 않았다.
- 독립 코드·운영 안내 검토 승인. 추가 배포 차단 사항은 발견하지 못했다.

## 실제 공개 후 남은 확인

ngrok 계정·Windows agent 설치·토큰 등록·실제 할당 주소·Vercel 계정 설정은 수행하지 않았다.
`your-assigned-name.ngrok-free.dev`는 빌드 확인용 예시이며 실제 연결하지 않았다.
Vercel에서 실제 BACKEND_ORIGIN 설정 후 Redeploy하고, 공개 health JSON·HTTPS 로그인/
로그아웃·두 브라우저 채팅·2분 이상 유휴 SSE·필요한 실제 Qwen/공급자 결과를 확인해야 한다.
로컬 빌드 성공을 실제 Vercel/ngrok 경유 검증으로 기록하지 않는다.

## 전달

설계/계획은 `afa3fd2`, Vercel 설정은 `89727bc`의 작은 설정 커밋으로 기록했다.
운영 안내는 `2ace0e8`에 기록했다. develop push가 성공했고 기존
[master ← develop PR #1](https://github.com/SEMI-CNU/trip-agent/pull/1)의 배포 설명을
ngrok 최종 구성으로 갱신했다. 이전 MVP·개발자 도구 설명은 보존했고 자동 merge하지 않았다.
실제 ngrok/Vercel 계정 설정과 공개 배포는 위 인수 확인 단계에 남아 있다.
