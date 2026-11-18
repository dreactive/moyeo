# 여행방 화면 통합 검증

2026-11-19 기준 `develop`의 `e6f4965b084dd5236f389fa9ef418913cfdbd272`에 `feat/front`의 화면 구성(`308079dbe60ced4321785b212d6cf32005cef25c`)과 여행방 관리 기능을 통합했다. 작업 브랜치는 `codex/integrate-front-layout`이다.

## 실행 결과

| 검증 | 실행 방법 또는 확인 대상 | 결과 |
| --- | --- | --- |
| 프론트엔드 | `node --test frontend/tests/*.test.js` | 266개 통과 |
| 백엔드 | `python -m pytest -c backend/pytest.ini backend/tests -q -o "addopts=-p no:asyncio"` | 통합 테스트 23개를 포함해 255개 통과 |
| AI | `python -m pytest -c ai/pytest.ini -p pytest_asyncio.plugin ai/tests -q` | 454개 통과, 1개 건너뜀 |
| Vercel 정적 빌드 | 테스트용 HTTPS 백엔드 주소와 공개 지도 키로 빌드 | 정적 파일과 `config.json` 생성. 페이지 별칭, 동일 출처 API 프록시, 캐시 방지 및 ngrok 헤더, 지도 키 주입 확인 |
| HTTP | 격리된 SQLite를 사용하는 로컬 서비스에 세션 쿠키로 요청 | 28건 통과. 회원가입과 로그인, 초대와 코드 참가, 빈 방 설정, 방장 권한, 메시지 저장, 삭제 후 접근 거부, 로그아웃 및 페이지 별칭 확인 |

브라우저의 요청은 실제 FastAPI와 `local_ai`의 판단·도구 실행 경로를 거쳤다. 모델 응답에는 fake 모델을, 장소 데이터에는 fixture 공급자를 사용했다. 실제 GPU 추론, 외부 장소 공급자 응답, 실제 Kakao 지도 SDK의 성공 경로는 별도 검증 대상이다. 지도 SDK 연동은 테스트 대역으로 검사했다.

## 브라우저에서 확인한 흐름

- 회원가입 비밀번호 불일치 안내를 확인한 뒤 정상 가입했다. 이메일 초대를 포함해 방을 만들고 최초 설정을 저장했다.
- 채팅을 전송하고 새 초안을 작성했다. 참가자 버튼을 한 번 눌러 목록을 연 뒤에도 입력한 초안이 남았다.
- 장소 조회 요청의 진행 상태와 `target_places` 질문을 확인했다. 장소명을 직접 입력해 요청이 완료되는 것을 보고, 결과 버튼으로 `fixture:place-a`의 상세 카드를 열었다.
- 초대 코드로 방에 참가하고, 로그아웃 후 로그인과 새로고침을 거쳐 방에 다시 들어갔다.

## 첨부된 프론트엔드 기능 보존 점검

아래 표의 프론트엔드 구현 파일은 `frontend/src/`, 단위 테스트는 `frontend/tests/` 기준이다. 백엔드 파일에는 저장소 기준 경로를 표기했다.

| 확인 항목 | 구현 | 회귀 검증 |
| --- | --- | --- |
| 요청별 진행 기록 | `workspace-view.js`, `room.js`, `chat.js`가 작성자, 인용, 대상과 제외 대상, 완료·대기·실패, 취소·대체·미지원, 응답 및 결과를 표시한다. 원본 메시지 버튼은 채팅창을 열고 해당 대화로 이동한다. 전역 상태에 대기·일부 실패·보류 표시가 있다. | `readiness-view.test.js`, `room-controller.test.js`, `chat.test.js` |
| 부분 결과의 유효 기간과 여행안 우선순위 | `agent-results.js`가 참가자·조건·근거·여행안 버전 네 개를 확인한다. `route-view.js`, `cost.js`는 여행안이 없어도 현재 부분 결과를 별도 패널에 표시하고, 버전이 달라지면 배너에 이전 실행 근거만 남긴다. 검토안·확정안은 독립적으로 표시한다. | `readiness-view.test.js`, `route-room.test.js` |
| 불완전한 일정·비용 | `route-view.js`, `agent-results.js`, `cost.js`, `place.js`가 미배치 방문, 미조회 경로와 시각, 질문·충돌, 미확인 가격과 일부 날짜 영업시간을 표시한다. 알려진 소계와 미확인 건수, 최종 합계의 미확인은 구분한다. | `readiness-view.test.js`, `place.test.js`, `route-map.test.js` |
| 사람의 지지와 확정 | `agreement.js`, `plan.js`, `items.js`가 항목 버전, 선택된 항목과 동일한 확정 대상인지 확인한다. 일부·과반 지지, 반대 수, 철회 및 공식 확정을 글자로 표시한다. 지난 확정안의 배지는 새 여행안에 붙지 않는다. | `readiness-view.test.js`, `plan.test.js`, `items.test.js` |
| 열린 질문과 답변 계약 | `items.js`, `room.js`가 제공된 후보 또는 장소명, 공백을 정리한 지역명, 한국 시간대(+09:00)의 미래 출발 시각을 기존 `{value: 답변객체}`로 보낸다. 메뉴는 최신 초안의 장소를 사용한다. `backend/services/questions.py`가 소유권과 열린 상태를 확인하며, 조회 대상 답변은 방문 찬성표를 만들지 않는다. | `items.test.js`, `forms.test.js`, `readiness-view.test.js`, `backend/tests/test_request_results.py`, `backend/tests/test_question_answer_conflicts.py` |
| 지도 조회와 상세 조회 | `room.js`의 지도 좌표 요청은 `?location_only=true`를 사용한다. `backend/services/observations.py`가 저장된 관측만 읽는다. 선택한 장소의 상세·메뉴 요청은 같은 경로에 쿼리 없이 보낸다. | `route-room.test.js`, `place.test.js`, `backend/tests/test_upstream_room_integration.py`, `backend/tests/test_observations_places.py` |
| 지도 표시와 상태 갱신 | `map.js`, `kakao-adapter.js`, `room.js`는 번호가 있는 방문과 지역 관측 근거가 있는 언급·미배치 장소를 구분한다. 유효한 좌표와 경로선만 그리고 거리·시간·통행료·경로선 미확인을 표시한다. 지지 상태만 변하면 저장된 좌표·상세를 재사용해 지도·목록·상세 배지를 갱신한다. | `route-map.test.js`, `route-kakao.test.js`, `route-room.test.js` |
| 장소 선택과 늦은 응답 | `state.js`, `place.js`, `room.js`가 현재 부분 일정과 요청 결과의 장소 선택을 보존한다. 상세 요청 번호, 방, 장소 및 확정 대상을 확인해 이전 응답을 폐기한다. 같은 버전에서 부분 일정이나 요청 결과가 교체되어 선택 근거가 사라지면 상세 카드와 지도의 로딩·재시도 상태도 해제한다. | `state.test.js`, `place.test.js`, `readiness-view.test.js`, `route-room.test.js` |
| 새 레이아웃의 연결 | `frontend/index.html`, `frontend/styles.css`, `room.js`에 지도 범례, 부분 일정·비용 링크, 날짜·장소·원본 대화 버튼, 질문 폼을 연결했다. 떠 있는 채팅과 날짜 메뉴, 읽지 않음, 작성 중 초안, 저장 중 버튼, 방장 설정, 숙소 수동 좌표와 고정비 편집을 유지한다. | `room-controller.test.js`, `chat.test.js`, `chat-dates.test.js`, `chat-unread.test.js`, `fixed-costs.test.js`, `place-picker.test.js`, `pending.test.js` |

## 백엔드 및 배포 경계

- `backend/services/agent_jobs.py`는 최신 결정 상태를 실행 전·적용 전에 검사한다. 삭제된 방의 결과와 재등록 요청을 버리면서 다음 방 작업을 처리한다. 추출 문맥, 실패 격리, 수동 재시도, 빈 메시지 작업 억제는 `test_agent_jobs.py`, `test_agent_staleness.py`, `test_extraction_recovery.py`, `test_upstream_room_integration.py`에서 확인했다.
- `backend/services/rooms.py`의 지역별 장소 연결, 방장 정보와 기존 방의 첫 참가자 대체 규칙, 방 목록·초대·삭제를 확인했다. 삭제 시 SSE 종료 알림만 남고 대화 이벤트·확정 이력·작업 기록은 정리된다. 날짜 대체는 에이전트와 직접 장소 상세 조회에 전달하는 설정 사본에만 적용한다. 관련 검증은 `test_front_integration_review.py`, `test_auth_rooms.py`, `test_observed_item_places.py`에 있다.
- `frontend/scripts/deployment.mjs`와 백엔드 정적 라우트의 로그인·회원가입·방 목록 별칭, `COOKIE_SECURE`, 동일 출처 API 프록시를 `frontend/tests/deployment.test.js`, `backend/tests/test_static_frontend.py`, `backend/tests/test_auth.py`에서 확인했다.

## 독립 리뷰 재검증

공유 질문에 두 사용자가 답변하면 두 번째 요청은 HTTP 409를 받고, 첫 답변·버전·이벤트·작업 수는 보존된다. 최신 초안의 메뉴 선택, 실행 중 재계획 버튼의 중복 제출 방지, 입력란을 떠날 때 참가자·초대 버튼의 클릭 유지도 확인했다. 마지막 장소 상세 회귀는 실제 화면 컨트롤러를 통해 부분 일정 또는 요청 결과를 교체하고, 응답 전후에 빈 선택 상태가 유지되는지 검사한다. 검토자가 프론트엔드 관련 5개 모듈을 다시 실행해 67개 테스트 통과를 확인했다.
