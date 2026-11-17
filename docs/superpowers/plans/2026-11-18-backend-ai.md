# Backend·AI 합본 계획 전환 안내

2026-11-18 사용자 요청에 따라 기존 순차 합본 계획을 **세 세션 독립 계획**으로 분리했다. 이 파일은 이전 링크의 진입점이며 구현 작업 목록으로 사용하지 않는다.

- [3세션 총괄 계획](2026-11-18-three-session-plan.md): 소유권, 독립 환경, 테스트 대역, 통합 게이트, 세션별 시작 지시문.
- [S1 FE 계획](2026-11-18-frontend.md): frontend 소유, Backend 없는 fixture 개발.
- [S2 BE 계획](2026-11-18-backend.md): backend 소유, 자체 FixtureAgentPort와 최종 통합.
- [S3 AI 계획](2026-11-18-ai.md): ai 소유, 독립 JSON 재생·모델·공급자·계산.
- [계약 v0.2](../../contracts/travel-api.md), [동결 JSON 예제](../../contracts/examples/README.md), [공통 검증표](../../testing/mvp-checklist.md).

## 이전 작업의 새 소유자

| 이전 작업 | 새 소유 세션·단계 |
|---|---|
| B0 공급자·모델 확인 | S3 A1. S1/S2의 시작 조건이 아님 |
| B1 계정·방·대화·SSE | S2 B1/B2 |
| B2 색상·동의·질문·충돌 선택 | S2 B3, S1 F3 표시 |
| B3 장소·경로·시간표·비용 계산 | S3 A2, S1 F4 표시 |
| B4 추출·후보·Agent 실행 | S3 A3/A4 |
| B4 결과 저장·버전·개발자 trace API | S2 B4 |
| B5 대화 재생·실제 모델/공급자 확인 | S3 A5 및 S2 G2-G4 통합 |

Backend가 ai/contracts.py를 직접 import하거나 두 세션이 루트 의존성/공통 체크리스트를 동시에 수정하는 이전 방식은 폐기한다. 기존 C01-C47 기능 기준은 유지한다. 현재 변경은 문서 개정이며 코드·설치·API·Git 작업을 수행한 것이 아니다.
