# Vercel + Cloudflare Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 개인 PC 서버를 유지하면서 환경 변수만 입력하면 Vercel 배포를 준비할 수 있게 한다.
**Architecture:** 정적 Vercel Build Output API → 고정 HTTPS Tunnel → 단일 FastAPI worker.
**Tech Stack:** Node ES modules, FastAPI, SSE, SQLite, Cloudflare Tunnel.
**Spec:** `docs/superpowers/specs/2026-11-18-vercel-cloudflare-design.md`

## Global Constraints

- backend는 한 worker, localhost:8000이며 기존 cookie·상대 `/api`·SSE 재생 계약을 유지한다.
- 서버 비밀값은 브라우저와 배포 산출물에 포함하지 않는다.
- 실행 로직 약 300자를 목표로 작은 검증·커밋 단위를 반복한다. 동작과 회귀 테스트의
  자연스러운 단위를 보존해야 할 때 조금 초과한 이유를 작업 기록에 남긴다.
- 기존 사용자 문서는 보존하고 develop의 이번 변경만 stage한다.
- 실제 외부 배포·유료 API 호출은 하지 않는다.

## Review Focus

- 유휴 SSE와 cursor 재연결: comment가 ID를 바꾸지 않고 즉시/15초마다 전달되는지 확인.
- HTTPS cookie: 로그인과 로그아웃의 flag 일치, 로컬 HTTP 호환을 확인.
- API 오류/429의 no-store와 거절 전 상태 불변, GET·SSE 예외를 확인.
- 악의적/누락된 origin·HTML 특수문자 키와 서버 비밀값 산출물 미포함을 확인.
- Vercel build root, `/api` prefix, `/dev`, 정적 자산과 환경 변수 누락 오류를 확인.

### Task 1: SSE 유지

**Files:** backend/services/events.py, backend/tests/test_events.py
**Interfaces:** 기존 `room_event_stream(db, room_id, after_seq)` 유지.
- [ ] 초기 heartbeat/cursor 테스트를 먼저 실행해 실패를 확인하고 최소 구현 후 검증·커밋.
- [ ] 주기 heartbeat를 제어된 시간으로 검증하고 구현·커밋.

### Task 2: 공개 HTTP 설정

**Files:** backend/config.py, backend/app.py, backend/routes/auth.py,
backend/public_http.py, backend/tests/test_public_http.py, backend/.env.example
**Interfaces:** COOKIE_SECURE, PUBLIC_REQUESTS_PER_MINUTE(60, 0=비활성).
- [ ] HTTPS cookie·logout 동작 테스트 RED → 설정/호출 GREEN → 커밋.
- [ ] API 응답과 오류 no-store 테스트 RED → middleware GREEN → 커밋.
- [ ] 분당 제한·GET 예외·새 window 회복 테스트 RED → 구현 GREEN → 커밋.
- [ ] `/api/health` JSON과 DB 가용성 테스트 RED → 구현 GREEN → 커밋.

### Task 3: 환경 변수 기반 정적 배포

**Files:** frontend/vercel.json, frontend/scripts/deployment.mjs,
frontend/scripts/build.mjs, frontend/tests/deployment.test.js,
frontend/.env.example, .gitignore
**Interfaces:** BACKEND_ORIGIN, KAKAO_JAVASCRIPT_KEY → .vercel/output/config.json + static/.
- [ ] HTTPS origin 검증 테스트 RED → 구현 GREEN → 커밋.
- [ ] 출력 경로·캐시 헤더·공개 키 escape 테스트 RED → 구현 GREEN → 커밋.
- [ ] allowlist 복사와 실제 빌드 테스트 RED → 구현 GREEN → 설정과 커밋.

### Task 4: 운영 안내·통합 검증·전달

**Files:** docs/deployment/vercel-cloudflare.md, README.md,
docs/verification/deployment.md
- [ ] Cloudflare/Windows/Vercel/Kakao 설정과 점검·문제 해결을 문서화.
- [ ] Backend/FE 회귀와 임시 origin·public key의 실제 build를 실행.
- [ ] 독립 검토 후 필요한 수정, diff·staged·비밀값 점검, 작은 커밋 마감.
- [ ] 로컬 규칙에 따라 develop push와 master 대상 기존 PR 갱신/생성 시도.
