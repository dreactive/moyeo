# 동결 계약 예제 v0.2

이 폴더는 **문서용 JSON 예제**이며 실행 서버·모델·실제 장소 정보가 아니다. 세 세션은 상대 구현 없이 같은 입력/출력 형태를 검사할 수 있다. 원본은 읽기 전용이고 변형은 각자 frontend/fixtures, backend/tests/fixtures, ai/fixtures에 둔다.

| 파일 | 타입 / 사용 |
|---|---|
| [room-snapshot.example.json](room-snapshot.example.json) | RoomSnapshot. 4인·빨강/노랑·비용·입력 요청 표시 |
| [agent-input.example.json](agent-input.example.json) | AgentInput. Backend 직렬화 출력 / AI 실행 입력 |
| [agent-result.example.json](agent-result.example.json) | AgentResult. AI 실행 출력 / Backend 가짜 Agent 결과 |
| [place-details.example.json](place-details.example.json) | PlaceDetails. 가상 A식당의 메뉴·가격·시간 |
| [place-details-b.example.json](place-details-b.example.json) | PlaceDetails. 가상 B공원. 두 방/장소 참조 복원과 두 지도 입력용 |
| [run-trace.example.json](run-trace.example.json) | RunTrace. call_id로 연결된 도구 호출/결과 |
| [edge-cases.json](edge-cases.json) | unsupported, stale, 임시 client_ref 치환, 충돌 선택의 데이터 변형과 기대 동작 |

- 모든 장소·주소·메뉴·가격·시간·경로는 가상이다. mode=fixture를 표시하고 실제 API/Qwen 검증에 포함하지 않는다.
- 스냅샷은 작성 중 예시여서 둘째 날 일정이 비어 있고 validation=needs_input이다. 이것을 완성 여행안이나 확정 가능한 상태로 간주하지 않는다.
- content_hash의 반복 a 값은 opaque 문자열 예시다. 실제 확인 테스트에서는 Backend가 정규화한 내용에서 SHA-256을 계산한다.
- get_place_details 관측은 제품 데이터다. trace를 읽어 제품 데이터를 복원하지 않는다.
- edge-cases의 *_patch는 기준 예제의 최상위 키를 교체하며 배열은 통째로 교체한다. message_replacements는 같은 ID의 recent_messages에 적용한다. 이는 제품 API의 별도 patch 연산자가 아니다.
- new-client-ref는 임시 ID를 support_observations·질문 target_ref/related_item_ids에 같이 사용한다. Backend가 실제 item ID를 배정하고 연결된 참조를 한꺼번에 치환한다.
- needs_input은 기본 결과 예제로, unsupported는 edge-cases의 결과 변형으로 검증한다. 정상 done/전원 확인/충돌 재계산은 각 세션의 자체 시나리오에서 명시적으로 구성한다.
- S1은 자기 fixture transport에서 상태 전이를 구현한다. S2의 가짜 Agent는 task의 run_id/room_id/base_versions를 결과에 반영하고 표본 메시지/ID를 명시적으로 사용한다. 가짜 Agent가 임의 한국어를 이해한다고 주장하지 않는다.
- S3는 모델 없이 fake/fixture 실행을 먼저 검증하고 실제 모델·공급자 결과와 별도 기록한다.

이 예제들은 DTO 이름·값 종류·참조 관계를 공유하는 최소 표본이다. 필드와 enum의 최종 기준은 [공통 계약](../travel-api.md)이다. 루트 예제를 바꾸는 계약 변경은 S2 통합 담당자가 조정한다.
