# Frontend

계약 v0.2, HTML/CSS/ES modules. npm이 없는 환경에서도 Node 직접 실행으로 동작합니다. 의존성 설치와 빌드 과정이 없습니다. Node 24 및 JSON module import를 지원하는 최신 브라우저를 기준으로 합니다.

```powershell
cd frontend
node server.js
node --test tests/*.test.js
```

- fixture: [사용자 화면](http://localhost:5173/?mode=fixture), [개발자 trace](http://localhost:5173/dev?mode=fixture).
- live: Backend가 같은 origin에서 index.html, /src, /fixtures, /styles.css, /dev를 제공합니다. FE 요청은 상대 /api 경로와 same-origin cookie를 사용합니다. 별도 CORS/프록시가 필요 없습니다.
- mode=fixture를 명시한 경우만 개발 데이터가 사용됩니다. live 오류는 짧은 오류와 재시도 동작으로 남고 자동 전환하지 않습니다.
- Python이 설치돼 있으면 python -m http.server 5173 --directory frontend로도 사용자 화면을 열 수 있습니다. 이 경우 개발자 화면은 /dev.html?mode=fixture입니다.
- 로그인의 이름/이메일/비밀번호는 서버 cookie 인증에 쓰입니다. user_id를 요청 body에 보내지 않습니다. 여행방 ID만 sessionStorage에 보관합니다. 개발자 token과 비밀번호는 저장하지 않습니다.
- 질문은 카드에 표시된 field/target_ref의 JSON 예제로 응답합니다. 위도/경도·메뉴 수량/공유·체류시간·조건 값·지지 대상을 바꿔 보낼 수 있습니다.

## 개발 시나리오

상단 fixture 표식은 항상 유지됩니다. 사용자 전환과 시나리오 선택은 개발용입니다. 임의 한국어 대화를 해석하거나 실제 다수결/계획 계산을 하는 대체 Backend가 아닙니다.

1. 01 초기: A 빨강 1/3, B 노랑 3/3, 체류시간 질문.
2. 02 조회/경비: 서버 DTO 예산 20만원/기지출 8만원/예정 7만원 → 앞으로 쓸 금액 12만원/계획 후 여유 5만원.
3. 사용자 u1→u2→u3로 바꾸며 전체 여행안 확인: 3/4 미확정. u4 확인: 같은 target 4/4와 기록된 서버 확정 상태.
4. 04 새 초안: 검토 revision 1 및 3표 유지, 새 초안 revision 2. ‘새 안으로 전환’은 revision 2/0표. 새 target의 확인은 별도 기록을 사용합니다.
5. 06 참가자/조건/근거 version 변경: 확인 종료, 과거 확정 스냅샷 유지.
6. 07 충돌: B 노랑 + !, u4 필수 조건. 다른 사용자는 개인 조건 완화 버튼을 누를 수 없습니다. 허용 대안은 새 초안만 만듭니다.
7. 09 미확인 비용, 10 시가/공유메뉴/기준일 없음, 11 메뉴 없음, 12 모든 질문 입력 형태.
8. 장소 버튼 선택 후 재연결 재생: 선택 상세 유지, 전체 동선/공동 version 불변.
9. trace: fixture-dev token, 잘못된 token, run-fixture 필터를 비교합니다. 후보/비교 점수/도구/정규화 결과/반영 결과는 네 event와 call-fixture로 연결됩니다.

fixture 입력은 원시 값 echo와 정해진 DTO 전이입니다. 새 입력에 대한 실제 재계획, 세션 인증, 다중 브라우저 전달, 소유권 보안은 Backend 통합에서 검증해야 합니다. ‘재연결 재생’은 최신 스냅샷 재조회이며 실제 네트워크 단절/복구 성공을 뜻하지 않습니다.

## 지도

index.html의 meta[name="kakao-map-app-key"] content에 **공개 JavaScript 키**를 설정합니다. [Kakao 공식 가이드](https://apis.map.kakao.com/web/guide/)에 따라 localhost:5173 및 실제 서비스 origin을 허용 SDK 도메인으로 등록합니다. REST/API 비밀 키를 넣지 않습니다.

키가 없으면 두 독립 adapter가 좌표·날짜별 방문 순서·서버 polyline/거리m/시간초/통행료를 표시합니다. 키가 있으면 SDK로 별도 지도/마커와 서버 polyline을 그립니다. 개인 장소 조회는 공동 상태를 바꾸는 API를 호출하지 않습니다. SDK와 실API는 실제 키가 없어 미검증이며 adapter 대역 통과를 live 지도 성공으로 기록하지 않습니다.

## S2 인계

frontend/**와 docs/verification/frontend.md만 가져옵니다. Backend/AI/공용 계약/루트 설정 변경은 없습니다. 동결 DTO가 원본이며 과거/검토 항목명은 item_snapshots를 씁니다. 초록은 표시안과 confirmed_plan의 target 및 item_version이 일치할 때만 보입니다. 불일치 시 중립 ‘새 안 · 미확정’이고 FE가 지지 수로 색상을 계산하지 않습니다.

[검증·커밋 기록](../docs/verification/frontend.md)의 G3/G4 미검증 항목을 이어서 확인합니다. 최종 develop push와 master PR은 S2 담당입니다.
