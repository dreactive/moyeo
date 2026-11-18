# Free ngrok Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 기존 Vercel 배포를 무료 ngrok 고정 주소로 연결할 수 있게 설정·안내를 맞춘다.
**Architecture:** 기존 정적 Build Output API의 외부 `/api/*` route에 ngrok용 요청 헤더 transform만 추가한다.
**Tech Stack:** Vercel Build Output API v3, Node 24, 기존 FastAPI/SSE, ngrok agent.
**Spec:** `docs/superpowers/specs/2026-11-18-ngrok-deployment-design.md`

## Global Constraints

- 기존 로그인 cookie·상대 API·SSE·backend/AI 코드는 유지한다.
- 개인 설정과 기존 Qwen/UI 미추적 파일은 stage하지 않는다.
- 토큰을 요청하거나 배포 산출물에 포함하지 않는다. 실제 설치/공개 배포는 하지 않는다.
- 실행 로직은 작은 단위로 검증·커밋하고 선언적 설정·문서는 온전하게 작성한다.

## Review Focus

- bypass header가 응답이 아닌 ngrok으로 향하는 요청에 적용되는지 확인.
- 같은 API route에서 EventSource와 fetch, `/api` prefix와 no-store가 유지되는지 확인.
- 무료 할당 domain과 임의 hostname 선택/유료 domain의 차이를 안내.
- PC API 전용 실행, 안전한 cookie, authtoken과 공급자 키의 PC 보관을 안내.
- 실제 계정·ngrok·Vercel 검증과 로컬 가상 origin build 검증을 구분.

### Task 1: Vercel 요청 설정

**Files:** frontend/scripts/deployment.mjs, frontend/.env.example
- [x] API route의 선언적 request.headers transform과 ngrok 예제 origin 추가.
- [x] 기존 FE 전체 회귀 및 ngrok 예제 origin 실제 build를 확인하고 커밋.

### Task 2: 사용자 설정 안내

**Files:** docs/deployment/vercel-ngrok.md, README.md, frontend/README.md,
docs/contracts/travel-api.md, docs/deployment/vercel-cloudflare.md,
docs/verification/ngrok-deployment.md
- [x] 설치·로컬 인증·주소 확인·Vercel 설정·Kakao·인수 확인·무료 한도를 문서화.
- [x] 기본 안내를 ngrok로 연결하고 Cloudflare는 소유 도메인용 대안으로 표시.
- [x] 독립 검토, diff와 비밀값/개인 설정 미포함 확인 후 문서 커밋.
- [ ] develop push, 기존 master 대상 PR 갱신 및 전달 결과 기록.
