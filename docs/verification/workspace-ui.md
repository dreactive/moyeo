# 여행 작업방 UI 구현·검증

- 날짜: 2026-11-18 (Asia/Seoul).
- 작업 브랜치: `codex/workspace-ui`, 별도 native worktree.
- 시작 기준: `develop` `2cddfbd`. 승인 설계: [화면 설계](../superpowers/specs/2026-11-18-workspace-ui-design.md).
- 통합한 원격 기준: `b033580`의 Vercel 기반 변경(`fed2c9a`), 이어 `1f8a33c`의 무료 ngrok 전환(`3d73776`). 모두 충돌 없이 병합했다. 마지막 통합 후 FE 169개를 다시 확인했다.

## 구현 결과

| 화면 | 주소 | 동작 |
| --- | --- | --- |
| 로그인 | `/login.html` | Cookie 인증, 오류 안내, 성공 후 반드시 방 선택 |
| 회원가입 | `/signup.html` | 별도 문서, 비밀번호 확인, 가입 세션으로 방 선택 |
| 방 선택 | `/rooms.html` | 방 만들기/참가 선택, 성공 응답 후에만 메인 이동 |
| 메인 | `/` | 좌측 채팅, 우측 조건·동선·개인 장소·경비, 상태 배너·동의 바 |

기존 같은 origin API, 방별 SSE 한 연결, 검토 대상의 전체 target, 서버 비용 계산을 유지한다. 사용 중 세션 만료는 작성 중 텍스트를 보존하며 재로그인을 안내한다. 초기 인증 거절과 네트워크 오류, 저장한 방의 접근 거절을 구분한다.

메시지는 기존 DOM을 재사용하며 한국 시간으로 묶는다. 한글 조합 중 Enter, 중복 Enter/클릭, 응답 대기 중 다음 초안, 이전 대화 보존을 처리한다. 개인 날짜·장소는 공동 계획을 수정하지 않는다. 필수 조건은 소유자만 수정·확인한다. 같은 안의 3/4는 미확정이고 공식 확정 스냅샷을 받은 뒤에만 확정을 표시한다.

## 자동 검증

| 범위 | 명령 | 결과 |
| --- | --- | --- |
| FE 전체 | `node --test frontend/tests/*.test.js` | 169 passed |
| Backend 독립 | `python -m pytest -c backend/pytest.ini backend/tests -q` | 136 passed, integration 23 deselected |
| Backend 통합 | `python -m pytest -c backend/pytest.ini backend/tests -q -m integration` | 23 passed |
| AI 회귀 | `python -m pytest -c ai/pytest.ini ai/tests -q` | 113 passed |

합계 441개 통과. Python은 저장소의 기존 integration 환경을 검증 인터프리터로만 사용했다. Backend에는 기존 Starlette/httpx 사용 중단 예정 경고가 한 번 출력되며 실패는 없었다. 실제 Qwen 추론·외부 공급자 품질 검증을 이 결과에 포함하지 않는다.

Vercel 실제 빌드 함수로 새 HTML 3개와 `workspace.css`의 산출물 포함, 공개 키 주입, `/api/*` proxy, 이전 산출물 정리, 환경 파일·서버·테스트 코드의 배포 제외를 확인했다. 배포 관련 회귀 6개는 FE 전체 결과에 포함한다.

## 브라우저 확인

별도 검증 서버 `127.0.0.1:8426`, 전용 `.data/ui-verification.sqlite3`, fixture Agent를 사용했다. 기존 방 DB·GPU·다른 작업 서버를 사용하거나 변경하지 않았다.

- 실제 HTTP cookie: 잘못된 로그인 안내, 회원가입 비밀번호 불일치, 가입 후 방 선택, 새 방 생성 후 메인, 새로고침 복원.
- 실제 HTTP cookie: 로그아웃 → 로그인 → 방 선택 → 초대 코드 참가 → 메인 재진입.
- 별도 인증 HTTP 클라이언트의 참가 및 메시지가 브라우저에 SSE로 전달됨. 참가 인원과 대화가 갱신됨.
- 실제 Enter 전송이 하나의 말풍선으로 표시되고 다음 입력 초안이 유지됨.
- 여행 설정 상단/하단 닫기, 예산 수정 저장 및 재열람 확인.
- 명시적 fixture: 방 생성의 지역·날짜·이름이 새 문서에서도 유지됨. 사용자·시나리오도 복원됨.
- 명시적 fixture: 같은 target 3/4 검토 중 → 네 번째 동의 → 4/4 공식 확정, 확정 항목 상태 확인.
- 명시적 fixture: 경비 상세를 펼친 채 메시지를 보내도 펼침 상태 유지.
- 날짜별 동선, 개인 장소 조회, 반복 방문 장소의 현재 선택일 유지, 장소 제목 64px 폭과 주소 줄바꿈 확인.
- 869×1206: 참조 화면의 30%/70% 분할과 네 카드. 1440×900: 채팅 360px·카드 약 502px. 390×844: 한 열 배치, 가로 넘침 없음(스크롤바를 제외한 client width 375px).
- 로그인·가입·메인 JPEG 결과물을 Codex 로컬 시각 산출물에 저장했다.

실제 Kakao 키·허용 도메인 연결은 실행하지 않았다. SDK 대역 테스트와 키 없는 좌표 대체 화면을 확인했다. 대체 화면을 실제 지도나 live 공급자 조회 성공으로 취급하지 않는다. `/dev` trace 회귀 테스트는 FE 전체에서 통과했다.

## 리뷰와 수정

독립 리뷰에서 확인한 방 생성/참가 경합, 손상 fixture 복원, BFCache 세션 복원, 키보드 중복 전송, 다음 초안 삭제, `seq`만 변경된 카드 재렌더링, 설정 하단 닫기, 장소 실패·재시도, 이전 대화 손실을 각각 작은 회귀 단위로 수정했다. 재계획 요청 중 배너가 버튼을 다시 활성화하는 문제도 수정 후 재검토했다.

전체 리뷰의 P2 5개 및 후속 pending-lock P2는 모두 해결 판정을 받았다. Vercel 통합과 늦게 도착하는 참가자 이름 수정도 별도 검토에서 추가 P1/P2가 없었다. 공개 작업방에는 원시 target JSON이나 개발자 토큰을 노출하지 않는다.

## 계약·협업 경계

- 최신 통합 기준 대비 자체 변경은 `frontend/**` 및 이 UI의 설계·계획·검증 문서다. `backend/**`, `ai/**`, 동결 계약에는 자체 변경이 없다.
- 진행 중인 `codex/grounded-qwen-extraction`의 AI·Backend·스키마 파일을 수정하거나 그 브랜치를 병합하지 않았다.
- 원격 배포 작업의 기존 `.gitignore`, Backend HTTP 설정, SSE 유지 신호, secure-cookie 설정을 보존했다. 새 화면이 Vercel allowlist에서 누락되는 접점만 `e699e9b`로 보완했고, 이후 ngrok upstream request transform도 보존했다.
- 새 기술 의존성이나 React를 추가하지 않았다. HTML/CSS/문서 외 실행 로직은 작동하는 작은 기능별로 테스트하고 커밋했다. 기능 경계를 위해 목표 분량을 넘긴 경우 커밋 본문에 이유를 남겼다.
- 개인 `AGENTS.md`, `.local/skills/trip-agent-small-commits/`, `.planning/`은 기존 ignore 규칙을 유지했다. 다른 작업의 미추적 문서는 보존했다.

원격 push 및 PR 결과는 최종 마감 보고와 PR을 참조한다. 실제 확인되지 않은 원격 전달을 완료로 기재하지 않는다.
