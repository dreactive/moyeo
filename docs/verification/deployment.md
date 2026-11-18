# Vercel + Cloudflare 배포 준비 검증

2026-11-18, 코드 기준 `9761d49` 및 이후 문서 커밋.
구현·검증은 develop에서 수행했으며 기존 미추적 Qwen/UI 문서는 포함하지 않았다.

## 완료한 코드와 설정

- SSE 최초 응답과 15초 주기 comment. 이벤트 ID와 Last-Event-ID 재생은 유지한다.
- `COOKIE_SECURE`로 HTTPS 세션 설정, `/api` 응답·429·예상하지 못한 500 no-store.
- 단일 프로세스의 rolling 60초 변경 요청 예산. 기본 60, 0은 비활성이다.
  인증 전 거절도 포함하는 전역 제한이며 사용자별/지속 공격 방어 또는 GPU 용량 보장은 아니다.
- `/api/health`: DB 접근 가능 200, DB 불가 503. 실제 모델·공급자 성공을 뜻하지 않는다.
- `SERVE_FRONTEND=0` 공개 API 전용 실행. 로컬 기본값 1은 기존 화면을 유지한다.
- Node 24 빌드에서 Vercel Build Output API v3 생성. HTTPS origin 검증,
  공개 Kakao 키 escape, 정적 파일 allowlist와 이전 산출물 초기화.
- 서버 .env·모델·DB·개발자 token은 빌드 입력과 배포 파일에 포함하지 않는다.
- Cloudflare 계정/DNS/고정 tunnel/Windows 서비스, Vercel 변수와 Kakao 도메인 안내.

## 실제 실행한 검증

| 검증 | 결과 |
| --- | --- |
| Backend 기본 회귀 | 136 passed, 23 integration deselected |
| Backend-AI fake/fixture 연동 | 23 passed, 136 deselected |
| FE 전체 | 45 passed |
| 실제 build CLI | v3 config, `/api` prefix 유지, public map key 삽입 |
| 정적 출력 | dev.html, fixtures, index.html, src, styles.css만 공개 |
| 실제 localhost HTTP smoke | DB health, 가입/로그인/방 생성, SSE 15.06초 유휴 유지 뒤 메시지 수신, 로그아웃 통과 |
| 독립 코드 검토 | 정적 작업 파일 노출·500 캐시 헤더 누락을 RED→GREEN으로 수정 후 승인 |

Node 24.22.1을 사용했다. Backend 테스트는 기존 BE 가상환경(Python 3.13.9)을 재사용했다.
이 테스트는 fake/fixture 검증이며, 실제 Qwen 운영에는 기존 Python 3.12 모델 환경을 유지한다.
제한 shell의 asyncio 테스트 중단 현상은 기존 기록과 같아 해당 실행을 종료하고
승인된 확장 shell에서 검증했다. 의존성·모델 설치나 기존 Qwen 환경 변경은 없었다.
테스트 라이브러리의 기존 Starlette/httpx deprecation warning 1개가 있었다.

회귀 명령:

```powershell
node --test frontend/tests/*.test.js
# python 경로는 기존 Backend 테스트 환경 실행 파일로 대체한다.
python -m pytest -c backend/pytest.ini backend/tests -q
# 실제 키 파일을 지정하지 않고 fake/fixture 환경을 사용한다.
python -m pytest -c backend/pytest.ini backend/tests -q -m integration
# frontend 디렉터리에서, 가상 origin과 공개 테스트 키를 사용했다.
node scripts/build.mjs
```

전체 테스트는 204개 통과했다. HTTP smoke는 별도 임시 SQLite와 fixture/fake로
실행했고 직접 만든 서버 프로세스 트리를 종료했다. 실제 공급자 호출은 없었다.

## 실제 배포 후 남은 인수 확인

Cloudflare/Vercel 계정 생성·도메인 구매·DNS 변경·실제 공개 배포는 수행하지 않았다.
빌드 확인의 `https://api.example.com`은 연결하지 않는 테스트 값이다.
실제 공개 도메인의 HTTPS cookie, 두 브라우저 채팅, 2분 이상 유휴 SSE,
실제 Qwen·공급자 결과와 PC 중지/복구는 운영자가 가이드대로 확인해야 한다.
PC 절전·인터넷·전원과 모델 지연, 단일 worker의 메모리 queue/관측 소실 제약은 유지된다.

## 커밋과 전달

설계/계획 `c2c458d`, 구현 범위 `418ef85..9761d49`를 작은 동작별로 기록했다.
HTTP·파일 시스템 설정이 필요한 동작의 동반 테스트는 약 300자 목표를 조금 넘기더라도
독립 실행 가능한 기능 경계를 우선했다.
`332aa9e`는 HTTPS 로그인·로그아웃 회귀 확인, `17dc94c`는 운영 문서 마감이다.
`develop` push가 성공했으며 기존 [master ← develop PR #1](https://github.com/SEMI-CNU/trip-agent/pull/1)의
기존 MVP 설명을 보존하고 각 템플릿 항목에 이번 변경·검증·남은 실제 배포 작업을 추가했다.
PR은 자동 merge하지 않았다. 실제 공개 배포는 운영 가이드의 사용자 설정 이후 단계다.
