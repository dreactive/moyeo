# 장소·메뉴 가격·영업시간 공급자 설계

- 조사일: 2026-11-18.
- 기준: [MVP 설계](../superpowers/specs/2026-11-18-travel-agent-design.md), [공통 계약](../contracts/travel-api.md).
- **현재 완료한 것은 공개 문서/스키마 조사다. 인증 데이터 API 호출, 여수 실데이터 검증, 유료 Actor 실행은 하지 않았다.**
- 사용자 지시: 가격·영업시간도 실제 API로 조회. Naver 연결이 어렵다고 판단되면 무료 API로 전환. 여수 데모를 부산으로 임의 변경하지 않는다.
- 병렬 구현에서는 공급자 probe/어댑터는 **S3 A1** 소유다. 아래 B0는 기존 타당성 단계의 이름이며 S1/S2의 선행 조건이 아니다. S3는 ai/.artifacts와 docs/verification/ai.md에 결과를 남기고 공용 공급자 문서는 S2가 취합한다.

## 1. 선택 순서

1. Apify HTTP API를 작은 여수 표본으로 검증한다. MCP 연결 자체를 선행 과제로 만들지 않는다.
2. 키 준비·연결·필드·동일 매장 매칭·커버리지에서 구현을 지연시키면 **무료 전남 J-TaaS API**를 사용한다. 무료 후보가 같은 요구를 충족하면 추가 수집 인프라를 만들지 않는다.
3. 관광지 운영시간·이용료는 무료 TourAPI의 실제 소개/반복정보 응답으로 보완한다.
4. 메뉴 가격 보완은 여수 음식메뉴/전국 착한가격 자동변환 API를 검증한다. 모든 업소를 포괄하는 데이터로 취급하지 않는다.
5. 후보가 없거나 값이 비면 missing으로 남긴다. fixture·수동 추정·사용자 입력을 실제 API 성공으로 바꾸지 않는다.

가격·시간의 확보 가능성이 모델 추출보다 먼저 확인돼야 한다. 메뉴명이 있다는 것과 메뉴 가격이 있다는 것, API에 가격 필드가 있다는 것과 여수 대상 업소에 실제 값이 있다는 것은 별개다.

## 2. 공급자별 확인 결과

### 2.1 Apify Naver Map Scraper

- [Actor 문서](https://apify.com/huggable_quote/naver-map-scraper), [생성 OpenAPI](https://apify.com/huggable_quote/naver-map-scraper/api/openapi).
- 커뮤니티가 운영하는 수집기이며 네이버 공식 API가 아니다. 표시 과금은 결과 1,000건당 $3부터이므로 무료 API로 소개하지 않는다. 가격·운영 상태는 실제 실행 시 다시 확인한다.
- 입력: searchKeywords:string[] 또는 urls:string[]. includeDetails=true, includeReviews=false로 필요한 매장 상세만 조회한다. maxItems로 표본 개수를 제한한다.
- 문서 출력: menus[].name/price(문자열), businessHours[].schedule의 day/start/end, place_id, 주소·좌표·placeUrl.
- 생성 스펙의 직접 호출 후보: `POST https://api.apify.com/v2/acts/huggable_quote~naver-map-scraper/runs`, 이후 run 상태와 dataset 결과 조회. 문서가 제공하는 동기 결과 endpoint도 있으나 시작·결과 조회 경계는 어댑터 안에 둔다.
- 동기 호출 경로는 [Apify 범용 API 문서](https://docs.apify.com/api/v2/actor-run-sync-get-dataset-items-post)와 Actor 생성 스펙의 표기가 달라 실제 실행에서 확인한다. 호출이 빠르다고 가정하지 않고 화면에는 조회 상태를 제공한다.
- [Apify MCP](https://docs.apify.com/mcp)는 Actor 실행·결과 조회를 도구로 노출한다. 현재 Agent의 registry 뒤에서는 HTTP와 MCP가 같은 PlaceDetails를 반환하도록 설계할 수 있다. MCP가 메뉴 누락을 해결해주지는 않는다.

### 2.2 무료 전남 J-TaaS 음식점 DB

[공공데이터포털 15111780](https://www.data.go.kr/data/15111780/openapi.do)은 무료 JSON OpenAPI로 안내한다. [공식 공급자](https://jeonnam.openapi.redtable.global/)에서 **전용 토큰**을 신청한다. 일반 공공데이터 serviceKey와 같은 키라고 가정하지 않는다.

[공식 정의서](https://jeonnam.openapi.redtable.global/front/docs/openAPI_docs_jeonnam.pdf)의 확인 내용:

| GET 경로 | 필요한 필드 | 사용 |
|---|---|---|
| /api/rstr/korean | RSTR_ID,RSTR_NM,ROAD_NM_ADDR,LOTNO_ADDR,RSTR_LAT,RSTR_LOT | 매장·주소·좌표 식별 |
| /api/menu/korean | RSTR_ID,MENU_ID,MENU_NM,MENU_PRC | 같은 매장의 메뉴·가격 |
| /api/rstr/oper | RSTR_ID,BIZ_HR_CN,HLDY_INFO_CN,RSTR_STTS | 영업시간·휴무·상태 |

세 응답은 RSTR_ID로 연결한다. serviceKey 필수, pageNo 선택, header/body[] 형태가 문서화돼 있다. 지역/키워드 서버 필터나 임의 page size 인자를 만들어 넣지 않는다. 문서에 없는 검색은 페이지를 확인하면서 여수 자료를 필터링한다.

중요한 제약:

- MENU_PRC와 시간·휴무는 선택 필드이고 null 응답 예시도 있다. 모든 매장에 있다고 보장하지 않는다.
- 공식 PDF의 갱신주기는 ‘기타(없음)’이며 포털의 실시간 표기와 다르다. 조회 시각과 데이터 기준일을 나눈다.
- 메뉴가격이 1인분인지 한상인지 제공 단위를 확인해야 한다.
- 필드 정의는 확인했지만 실제 여수 행·토큰 발급·데이터 제공 상태는 미확인이다.

### 2.3 무료 보완 후보

| 공급자 | 확인된 범위 | 이번 사용 조건 |
|---|---|---|
| [국문 TourAPI 15101578](https://www.data.go.kr/data/15101578/openapi.do) | 무료 관광정보, 소개/반복정보 조회 기능 | 관광지 운영시간·이용료를 실제 응답에서 확인. 음식점 메뉴명이 가격을 뜻하지 않음 |
| [여수 관광 음식메뉴 15040854](https://www.data.go.kr/data/15040854/fileData.do?recommendDataYn=Y) | 메뉴·한상가격·1인분가격, 자동변환 OpenAPI 안내 | 매장 조인키·API 실제 함수 경로·기준일을 B0에서 확인 |
| [전국 착한가격 15172358](https://www.data.go.kr/data/15172358/fileData.do) | 전국 지정 업소의 일부 메뉴·가격, 분기 갱신, CSV 및 자동변환 REST 노출 | 여수 해당 행과 동일 업소를 확인. 영업시간 제공 자료가 아님 |
| [부산 착한가격 메뉴 15145474](https://www.data.go.kr/data/15145474/openapi.do) | 부산 지정 업소 메뉴가격 API | 현재 여수 데모에는 사용하지 않음 |

전국 자료의 포털 노출 경로는 `GET https://api.odcloud.kr/api/15172358/v1/uddi:d45599dd-2090-4bbb-abde-dbe9f9c6e75a`다. 데이터 버전별 경로와 인증은 구현 시 포털 명세로 다시 확인한다. CSV를 REST로 제공해도 최신성이나 영업시간 누락이 해결되는 것은 아니다.

TourAPI의 세부 response key와 여수 자동변환 API의 함수명은 이 문서에서 확정하지 않았다. 구현자가 추측하지 않도록 B0에서 공식 현행 명세와 실제 응답을 기록한 뒤 어댑터 매핑을 결정한다.

## 3. 공통 정규화와 매장 매칭

모든 공급자는 계약의 PlaceDetails/Menu/OpeningHours/Evidence로 변환한다.

- Apify place_id나 전남 RSTR_ID를 provider_record_id로 유지한다.
- 같은 이름만으로 합치지 않는다. 주소·전화·좌표 중 확보한 독립 정보로 동일 매장을 확인하고 불명확하면 match_status=ambiguous로 돌려준다.
- price_text는 원문을 유지한다. 정확한 숫자만 price_krw로 변환하고 ‘시가’·변동가격·해석 불가 범위는 null과 원문으로 남긴다.
- 영업시간 원문·휴무를 보존한다. 방문일에 적용 가능한 시간 범위로 해석했을 때만 intervals를 채운다.
- Evidence는 source_url, retrieved_at, provider_updated_at, status, mode, match_status를 포함한다.
- 앱이 지금 조회해도 공급자 원자료 기준일이 오래되거나 없을 수 있다. ‘실시간 확정 가격’ 같은 문구를 자동 생성하지 않는다.

## 4. B0 실제 연결 검증

아래는 계획된 검증이며 아직 실행하지 않았다. 필요한 키를 준비한 뒤 첫 공급자 접근·샘플 정규화에 **최대 60분의 조사 구간**을 둔다. 이는 API 응답 제한시간이 아니라 구현 우선순위를 정하는 기준이다.

- [ ] Apify를 사용할 경우 표본 상한 5건·리뷰 제외로 준비하고 실제 응답 스키마를 기록한다. 키·사용 조건 준비가 지연되면 무료 후보 검증을 먼저 진행한다.
- [ ] 무료 전남 토큰으로 매장/메뉴/운영 endpoint를 읽을 수 있는지 확인한다.
- [ ] 여수 식당 최소 5곳을 조사해 **최소 3곳에서 동일 매장의 숫자 메뉴가격과 방문일 영업시간**이 함께 확인되는지 기록한다. 실제 1박2일 식사 슬롯과 예비 후보를 채우려면 표본을 더 늘린다.
- [ ] 여수 관광지 최소 2곳의 운영시간과 이용료 또는 명시적 무료 여부를 실제 응답에서 확인한다.
- [ ] 제공 단위·휴무·API 조회 시각·원자료 기준일을 기록한다.
- [ ] source 실제 값과 정규화 값, 동일 매장 판정 근거를 1:1로 대조한다.
- [ ] 주 공급자와 보완 공급자를 선택하고 선택 근거를 이 문서 하단 실행 기록에 추가한다.

판정은 `미실행 / 통과 / 필요한 필드·커버리지 미충족`으로 남긴다. 통과 전에도 FE와 도메인 개발은 fixture로 병행할 수 있지만, 실제 가격·시간 기능을 완료 처리할 수 없다.

## 5. 필요한 설정 이름

아직 .env.example 파일은 만들지 않았다. 구현 때 예시 이름으로 다음을 준비한다.

- KAKAO_REST_API_KEY, KAKAO_JAVASCRIPT_KEY: 장소·지도.
- KAKAO_MOBILITY_API_KEY: 자동차 경로용. 앱 설정상 동일 키를 쓰는 경우를 포함해 실제 설정 확인.
- PLACE_DETAILS_PROVIDER=apify 또는 jeonnam.
- APIFY_TOKEN: 선택 경로에서만 필요.
- JEONNAM_API_KEY: 전남 전용 토큰.
- TOURAPI_SERVICE_KEY, ODCLOUD_SERVICE_KEY: 사용하는 무료 보완 경로만 준비.

키 값은 문서나 trace에 쓰지 않는다. 모든 공급자를 한꺼번에 구현하는 것을 B0 통과 조건으로 삼지 않는다. 실제로 값을 확보한 **가장 작은 조합**을 선택한다.
