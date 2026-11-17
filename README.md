# 공동 여행 계획 웹 서비스

2026-11-17 서비스 기획과 2026-11-18 확정한 구현 범위를 기준으로 작업한다.

**기준 문서: [서비스 기획서 v1.0](./docs/travel-agent-service-plan.md)**

**최신 구현 기준: [MVP 설계](./docs/superpowers/specs/2026-11-18-travel-agent-design.md) · [공통 API 계약](./docs/contracts/travel-api.md)**

구현 세부가 기존 기획과 다르면 2026-11-18 설계를 따른다. 현재 산출물은 설계·개발 계획이며 서비스 구현 완료를 의미하지 않는다.

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

코드는 구현 때 frontend/, backend/, ai/로 나누고 docs/ 등은 공용으로 둔다. 기존 submission/과 원문 PDF는 보존한다.

`docs/`의 대회 안내 PDF와 `data/`의 기존 원본 자료는 보존한다. 원본 자료의 존재가 현재 서비스의 구현 범위를 정의하지는 않는다.
