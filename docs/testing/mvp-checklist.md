# MVP 기능 검증 체크리스트

- 기준: [설계](../superpowers/specs/2026-11-18-travel-agent-design.md), [계약](../contracts/travel-api.md).
- 세션 담당: [S1 FE](../superpowers/plans/2026-11-18-frontend.md), [S2 BE](../superpowers/plans/2026-11-18-backend.md), [S3 AI](../superpowers/plans/2026-11-18-ai.md). [병렬 총괄](../superpowers/plans/2026-11-18-three-session-plan.md)의 G1 독립 완료와 G4 실제 통합을 구분한다.
- 이 공통 체크리스트는 동결 기준이다. 각 세션은 [FE 기록](../verification/frontend.md) / [BE 기록](../verification/backend.md) / [AI 기록](../verification/ai.md)에 증거를 남기고, **S2만 통합 시 이 표를 갱신**한다. 통합 결과는 [integration 기록](../verification/integration.md)에 남긴다.
- 아래 표는 S2가 실제 실행 근거로 갱신한다. 체크는 기록한 모드의 관측 통과이며, fixture·replay 통과를 Qwen/live로 대체하지 않는다. 부분 검증·미실행은 체크하지 않는다.
- 각 항목을 실행하면 `날짜 / 모델·코드 버전 / fixture 또는 live / 실행 명령 또는 조작 / 관측 결과·증거 경로 / 담당자`를 남긴다.
- Backend 예외 체계가 아니라 사용자 기능·Agent 판단·데이터 근거·계산·동의 흐름을 검증한다.

## A. 실제 공급자와 모델 준비 — S3 A1, 최종 G4

- [x] C01. [공급자 B0](../providers/place-data.md)의 여수 가격·영업시간·동일 매장 검증을 실행하고 결과를 기록했다.
- [x] C02. Apify 연결이 어려운 경우 무료 API로 전환했고, 도시·업소 범위·누락을 실제 값으로 기록했다. 해당 전환이 불필요하면 미적용 사유를 기록한다.
- [x] C03. 관광지 2곳 이상의 API 운영시간·이용료 또는 명시적 무료 근거를 확인했다.
- [x] C04. 로컬 베이스와 현재 judge LoRA를 로딩하고 생성/판단 두 모드의 출력 및 실제 모델명을 기록했다. fake만으로 통과하지 않는다.
- [x] C05. 모델 구현을 fake 또는 다른 ModelBackend로 교체해도 runner/Backend/FE 계약이 바뀌지 않는다.

## B. 대화와 조건 — S2 B2/B4, S3 A3/A4, S1 F1/F2

- [x] C06. 4개 로그인 세션이 코드로 같은 방에 입장하고 참가 명단을 공유한다.
- [ ] C07. 한 사람이 POST로 보낸 메시지가 다른 세 화면에 SSE로 나타난다. 전체 페이지 새로고침은 필요 없다.
- [x] C08. Agent 출력은 오른쪽에만 나타나고 사람 채팅에는 AI 메시지가 없다.
- [x] C09. ‘예산 20만원’ → ‘아니 15만원’에서 같은 사람의 정정과 근거 메시지를 연결하고 이전 조건 이력을 남긴다.
- [x] C10. 다른 사람이 개인 필수 조건을 완화하는 발언을 해도 소유자 확인 없이 조건이 바뀌지 않는다.
- [x] C11. 잡담·같은 의견 반복은 실제 장소/가격/경로 호출 수를 늘리지 않는다. 필요한 새 조건은 반영한다.
- [x] C12. 필요한 출발지나 메뉴 제공 단위가 없으면 오른쪽에 입력 요청을 표시하고 값·가격을 만들어내지 않는다.

## C. 빨강·노랑·초록과 충돌 — S2 B3, S1 F3, S3 의미 추출

- [x] C13. ‘A식당?’을 언급하면 빨강이고 색상 외 ‘언급됨’ 라벨이 보인다.
- [x] C14. 4명 중 제안자와 다른 2명이 같은 항목을 명시 지지하면 노랑이다. 2명만이면 빨강이다.
- [x] C15. 같은 사람의 반복 지지는 1명이다. ‘다들 동의했어’가 타인의 지지를 생성하지 않는다.
- [x] C16. 대상이 불분명한 ‘좋아’는 임의 항목 지지로 연결하지 않는다. 철회·반대는 해당 사람 지지를 갱신한다.
- [x] C17. 다수 지지로 노랑이 되어도 공식 확인 인원이 늘거나 초록이 되지 않는다.
- [x] C18. 같은 여행안 target을 3명 확인하면 미확정이고, 4번째가 확인해야 계획과 포함 항목이 초록이다.
- [x] C19. 시간/예산/영업시간 충돌은 색상과 별도로 `!`·설명·영향 항목·선택지를 표시한다.
- [x] C20. 사용자가 충돌 대안을 선택하면 관련 일정·경로·경비를 다시 계산한다. 선택 자체로 확인 표를 생성하지 않는다.
- [x] C21. 해소되지 않은 blocking 충돌이나 필수 검증 미확인이 남으면 전원 클릭만으로 확정하지 않는다.
- [x] C22. 3명 확인 중 새로운 초안이 도착해도 review_plan의 내용·확인 대상은 유지된다. 새 안 전환 시 확인 표를 새로 모은다.
- [x] C23. 참가자/조건/실질 근거 변경은 이전 확인을 이어받지 않는다. 과거 confirmed_plan은 원래 스냅샷으로 남는다.
- [x] C24. 실제 항목이 바뀐 새 item_version에는 이전 항목의 대화 지지를 재사용하지 않는다.

## D. 지도·일정·가격·경비 — S3 A2, S2 B4, S1 F4

- [x] C25. 자동차 API가 반환한 거리·시간·경로가 날짜별 일정에 반영된다. 직선을 실제 도로 경로로 소개하지 않는다.
- [x] C26. 한 사람이 장소 상세나 지도 확대를 바꿔도 다른 사람의 개인 열람 상태는 바뀌지 않는다.
- [x] C27. 전체 동선 지도와 선택 장소 지도는 각각의 목적에 맞는 같은 장소 ID·여행안 버전을 사용한다.
- [x] C28. 메뉴와 시간은 같은 매장임을 확인한 API 근거에 연결된다. 동명이점의 메뉴를 붙이지 않는다.
- [x] C29. ‘시가’·공란·미등록 가격은 null/미확인이다. 무료라고 명시된 근거 없이 0원 처리하지 않는다.
- [x] C30. 메뉴가격의 단위·수량·인원 가정, 숙박·왕복 교통·기지출이 계산에 포함된다. 차량비의 포함·미확인 항목도 표시된다.
- [x] C31. 전체액·1인액·기지출·남은 예산·미확인 항목 수가 코드 계산과 일치한다. 미확인 비용을 뺀 소계를 완전 총액으로 표시하지 않는다.
- [x] C32. 장소를 바꾸면 일정·자동차 구간·예상 경비가 같은 새 계획 버전으로 갱신된다.
- [x] C33. source_url·조회 시각·공급자 기준일을 확인할 수 있고 fixture·API 값·사용자 입력·추정을 구별한다.

## E. Agent 실행과 개발자 확인 — S3 A4/A5, S2 B4/B5, S1 F5

- [x] C34. 실제 Qwen이 고른 후보가 실제 도구 호출을 결정하는 run을 확인했다. 미리 정한 고정 순서를 모델 판단으로 표시하지 않는다.
- [x] C35. 도구 결과에 따라 다음 도구·대안 조회가 달라지는 run을 확인했다.
- [x] C36. 필요한 정보가 충분한 요청, 정보 부족, 미지원 기능을 각각 도구 호출·입력 요청·미지원 표시로 구분한다.
- [x] C37. trace에서 run_id·step·call_id로 후보/선택 점수·도구 인자·정규화 결과·반영 버전을 연결해 볼 수 있다.
- [x] C38. 사용자 SSE·일반 API에는 개발자 trace가 없고 개발자 토큰을 가진 화면에서만 조회한다.
- [x] C39. 합성 대화 재생 결과에 조건 추출·지지 대상·판단·호출 수·소요 시간을 남긴다. fixture 결과와 live 결과를 다른 실행으로 기록한다.
- [ ] C40. 가상 4인 여수1박2일에서 귀가 시간 추가 → 충돌 `!` → 대안 선택 → 지도/경비 재계산 → 새 버전 전원 확인 → 초록 확정까지 시연했다.

## F. 인계와 완료 판정

- [x] C41. FE는 Backend 없는 fixture, BE는 AI 없는 FixtureAgentPort, AI는 BE 없는 JSON 재생으로 각각 독립 실행·검증한다. 세 결과와 최종 통합은 별도로 기록한다.
- [x] C42. 신규 실행자가 README의 설정·실행 순서로 frontend/backend/ai를 연결할 수 있다.
- [x] C43. 실제 연결하지 못한 공급자·미확인 데이터·측정하지 않은 모델 품질은 남은 항목으로 표시한다.
- [x] C44. 대회 제출 패키지와 서비스 실행 구성을 구분하고, submission 원본 및 대회 PDF를 보존했다.
- [x] C45. 입력 요청 카드에서 거점·메뉴/수량·체류시간·본인 조건 답변을 보내면 해당 대상에 반영되고 관련 재계획이 실행된다.
- [x] C46. 예산20만원/기지출8만원/미지출 예정7만원에서 앞으로 쓸 금액12만원, 계획 후 여유5만원을 구분한다. per_person·owner_id=null은 전원에게 각각 적용한다.
- [x] C47. 실제 도구 결과는 AgentResult.observations를 통해 장소 상세·근거·다음 실행에 전달된다. trace를 읽어 제품 데이터를 복원하지 않는다.

단계별 완료는 해당 계획의 체크와 관련 C번호의 관측 근거가 함께 있을 때만 표시한다. 독립 구현과 fake/fixture 연동은 검증했으며, 실제 Qwen/live G4와 최종 전달은 통합 기록의 별도 상태를 따른다.

## 실행 기록 양식

| 날짜 | C번호 | 모델·코드 버전 | 모드 | 실행/조작 | 관측 결과와 증거 | 판정 |
|---|---|---|---|---|---|---|

API 키 없는 개발용 fixture 검증, 허용된 실제 응답을 이용한 replay, 인증 live API 검증, 실제 로컬 모델 검증을 서로 대체하지 않는다.

## S2 통합 실행 판정 — 2026-11-18

기준: BE 4761c56(독립111), FE615172b(40), AI8c55e36(113), 합성 평가18/18. 최종 AI 인계는 반영했으며 G4 제품 흐름은 별도 판정한다. 실행 명령과 원문 결과는 각 verification 보고서와 통합 기록에 있다. 표의 모드·제한이 판정 범위다.

| C번호 | 판정·모드 | 실행·관측 근거 (담당 S2, AI/FE 독립 증거 포함) |
|---|---|---|
| C01 | PASS live/S3 | 실제 여수 식당5/카페1의 가격·시간 및 세 사업장 교차 매칭. AI 최종 보고의 B0 표와 실제 응답 재생; 조회 수/누락을 구분. |
| C02 | N/A recorded | Apify 인증 실행·동일 매장 결합이 성공해 무료 공급자 전환이 불필요했다. TourAPI/전남 키는 미준비·미선택으로 기록; 성공 대체 없음. |
| C03 | PASS live/S3 | 유월드·아쿠아플라넷의 API 이용권 가격과 방문일 운영시간 확인. 케이블카 가격은 있으나 시간 미확인으로 별도 남김. |
| C04 | PASS mechanics; quality limited | 실제 Qwen2.5-1.5B-Instruct 베이스 생성·현재 judge LoRA 점수 모드와 후보1/2/5 실측. 자유 추출 실패·rule-assisted 보조를 모델 품질 통과로 표시하지 않음. |
| C05 | PASS fake/fixture | AI runtime 계약·모델 대역 교체, BE lazy bridge 테스트. AI113 / BE111 / FE40; 실제 모델 동등 품질 주장 없음. |
| C06 | PASS HTTP fake/fixture | G2 test_empty_four_person_room_creates_initial_plan: 실제 가입 cookie 4개·코드 입장·동일 참가 명단. |
| C07 | PARTIAL HTTP fixture | G3 실제 TCP POST→다른 3 cookie SSE 수신 PASS, FE 중복 제거/자동 snapshot 복구 PASS. 부모 IAB 1화면 관측; 세 브라우저 화면 동시 시연은 별도 미관측. |
| C08 | PASS fixture + G2 | 사람 메시지 보존, agent.status/우측 UI. G2 JSON 적용 후 사람 채팅 원본 동일. |
| C09 | PASS rule-assisted fixture | AI test_rule_assisted_budget_correction_is_owned_and_grounded / Backend owner 확인·supersede 이력 테스트. 순수 모델 품질 통과 아님. |
| C10 | PASS structured fixture | BE consensus_constraints·questions 소유권, G2 u4 조건의 u1 confirm403/u4 confirm200. |
| C11 | PASS fake/fixture | AI runtime chat/chitchat·중복 호출 제외 테스트와 BE processed cursor. 실제 공급자 호출량 장기 측정은 아님. |
| C12 | PASS fixture | AI missing anchors/menu basis 테스트; FE 입력 카드 렌더; null 보존. 미확인 값을 만들어 ready로 표시하지 않음. |
| C13 | PASS rule-assisted fixture | AI question_form_mention_creates_item_but_never_support 통과; BE mentioned 상태와 FE 빨강·언급됨 라벨 검증. 순수 모델 언급 추출 품질 주장 아님. |
| C14 | PASS G2 fake/fixture | 제안자+1명은 mentioned, +2명은 supported. Backend 임계값3·FE 라벨/색상 렌더. |
| C15 | PASS G2 + unit fixture | 동일인 반복 후 supporter_ids3 유지, proxy·오래된 버전 source 거부. |
| C16 | PASS fixture | AI ambiguous/proxy 검증, BE support_target 원저자만 답변, oppose/withdraw 도메인 갱신. 공식 표 없음. |
| C17 | PASS G2 fake/fixture | 노랑에서 confirmations=[]; 대화 지지가 공식 확인을 만들지 않음. |
| C18 | PASS G2/G3 | 3명 동일 target 미확정, 4번째 확정; G3 IAB 동일 hash4/4 및 포함 항목 초록. |
| C19 | PASS fake/fixture | G2 귀가시간 blocking conflict, AI 시간/예산/휴일 검증, FE 기록 시나리오의 별도 !·설명·선택지. live G4 별도. |
| C20 | PASS G2 fake/fixture | 저장된 drop 선택→일정/경비 재계산·새 target·confirmations=[]; AI route 재계산 단위 테스트. |
| C21 | PASS fixture | BE test_blocking_or_unchecked_requirements_prevent_green, ready_to_confirm·본인 hard 조건 검증. |
| C22 | PASS fixture | BE frozen review/new draft/conflict 분리; FE controlled renderer/응답 경합 회귀. 활성화 시 표 새로 수집. |
| C23 | PASS fixture | BE 참가·조건·실질 근거 변경/불변 confirmed-history; FE615 세 basis 초록 제거 및 확인 비활성 회귀. 새 대안만의 근거는 옛 review 표 유지. |
| C24 | PASS fixture | BE item_changes_clear_previous_version_support; FE 다른 item_version으로 초록 비전이. |
| C25 | PASS real model/live component | S3 a9154f1에서 실제 날짜별 Kakao 미래 경로3개·거리/초/geometry 보존. 경유 출발은 직전 실제 소요시간 반영. G4 전체 제품 흐름은 별도. |
| C26 | PASS fixture/G3 | FE personal map adapter 분리·개인 선택; BE place GET 전후 계획/표 불변. 다중 사용자의 열람 상태는 공유 snapshot에 쓰지 않음. |
| C27 | PASS fixture/G3 SDK | 부모 IAB 전체/개인 두 실제 Kakao 지도, FE review 우선 target·같은 place_ref·서버 polyline 검사. |
| C28 | PASS recorded-live join | 이름·좌표·정규화 시군구/도로/건물번호로 덕수·모이핀·서울해장국 세 곳 실제 Kakao/Apify 응답 결합, 다른 상호 거부. 원문 주소·동일 매장 메뉴 근거 보존. |
| C29 | PASS fixture normalization | AI unknown_price_is_not_zero, explicit 무료 근거만 0; FE 시가·공란 null 표시. |
| C30 | PASS fake/fixture | AI cost_inputs/itinerary_costs: 단위·수량·전원 per_person·공유·기지출·차량 유류/주차/통행료; G2 명시 입력130000. |
| C31 | PASS fake/fixture | AI Decimal KRW 계산·미확인 total null·기지출 독립 보존; FE known subtotal/전체액 구분. |
| C32 | PASS fixture | AI replace/drop 선택 후 route/cost 재계산, BE 원자 plan 적용/새 hash·item_snapshots, FE 동일 snapshot 사용. 실제 변경 live G4 별도. |
| C33 | PASS fixture/G3 | FE source URL/조회·공급자 시각·mode 표시, BE observations provenance 보존. 공급자 기준일 없으면 null. |
| C34 | PASS local_qwen/live component | S3 실제5판단 모두 complete finite score array의 argmax 확인. tool_name/arguments=실제 tool_call; 단계4에서 독립 후보 중 calculate_costs를 먼저 선택. 고정 순서 아님. |
| C35 | PASS local_qwen/live component | 실제 route observation 추가에 따라 다음 날짜/출발시각의 get_car_route 후보·선택이 변경되고 계산 후보로 전환. 최종3 route IDs·geometry 보존. |
| C36 | PASS fixture + real ready | AI113 회귀에서 충분/부족/unsupported 분리. 실제 S3 local_qwen/live ready134000·unknown0. unsupported는 fixture 테스트 범위, 일반 언어 품질 확대 주장 없음. |
| C37 | PASS fixture/G2/G3 | 실제 runtime decision→tool_call/result→BE state_applied 연결. FE dev trace call_id/점수/상태 링크 테스트. |
| C38 | PASS HTTP fixture | G3 room cookie+X-Dev-Token 통과, 토큰 없음403; BE 일반 API/SSE trace 비노출·키 제거. |
| C39 | PASS separated evaluations | S2 fake/fixture 재생18/18, 최종 AI113; S3 local_qwen/live a9154f1 5tool·5assertion PASS·590.215초/정상 종료. 실제 start SHA/후속 산술 수정98117d4 구분. |
| C40 | PENDING local_qwen/live | G2 fake/fixture HTTP 전체 흐름은 PASS. S3 최종 인계·GPU 종료 후 별도 G4 예정; 실제 UI 전체 동시 시연은 아직 없음. |
| C41 | PASS independent | FE40 tests + standalone fixture, BE111 tests no ai/torch import, AI113 core fake/fixture JSON + 재생18/18; G2/G3와 별도. |
| C42 | PASS startup docs; limits stated | root·FE·BE·AI README 실행/선택 의존성/동일 origin/절대 env·로컬 모델 경로 안내. 최종 AI README 링크 해소, 부모 MD22/내부링크121 broken0. S2 실제 uvicorn local_qwen/live 기동·4로그인 확인; 최종 G4는 진행 중. |
| C43 | PASS provenance | 각 보고서가 fixture/replay/live와 rule-assisted 추출·미측정 모델 품질·미선택 공급자를 구별. 남은 G4 숨기지 않음. |
| C44 | PASS preservation review | 부모 전체 submission9파일·원본 PDF SHA 보존, baseline 대비 submission/data/PDF diff 없음. 서비스와 대회 패키지 구분. |
| C45 | PASS fixture/G2 | BE question field/target/owner·menu 소속 검증, FE typed 제출; G2 실제 menu answer 후 자동 재계획 ready130000. |
| C46 | PASS fixture arithmetic | AI budget_paid_and_projected_balances, shared_remainder_and_per_person_without_owner; FE 앞으로 쓸 금액/계획 후 여유 분리. |
| C47 | PASS G2 fixture/runtime | observations→DB 제품 메모리→다음 task/직접 장소 상세. trace disabled 상태도 정상; trace 복원 사용 안 함. |
