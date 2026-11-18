def test_probe_counts_only_live_yeosu_values():
    from ai.providers.probe import summarize
    rows = [
        {"region": "여수", "mode": "live", "match_status": "matched", "price_krw": 10000, "intervals": [{}]},
        {"region": "여수", "mode": "fixture", "match_status": "matched", "price_krw": 10000, "intervals": [{}]},
        {"region": "부산", "mode": "live", "match_status": "matched", "price_krw": 10000, "intervals": [{}]},
        {"region": "여수", "mode": "live", "match_status": "ambiguous", "price_krw": 10000, "intervals": [{}]},
        {"region": "여수", "mode": "live", "match_status": "matched", "price_krw": None, "intervals": None},
    ]
    report = summarize("test", "여수", rows)
    assert (report["matched_place_count"], report["priced_menu_count"], report["usable_hours_count"]) == (2, 1, 1)


def test_unknown_price_is_not_zero():
    from ai.providers.normalize import price_krw
    assert [price_krw(x) for x in ["10,000원", "0", 0, "시가", "", None, "1~2만원"]] == [
        10000, 0, 0, None, None, None, None]


def test_weekly_hours_expand_only_for_known_visit_days():
    from ai.providers.hours import expand_hours
    hours = [{"schedule": [{"day": "토", "start": "10:00", "end": "20:00"}]}]
    assert expand_hours(hours, ["2026-11-21", "2026-11-22"]) == [
        {"day": "2026-11-21", "start": "10:00", "end": "20:00"}]


def test_hours_breaks_are_not_open_intervals():
    from ai.providers.hours import expand_hours
    hours = [{"schedule": [{"day": "매일", "start": "10:00", "end": "21:00",
                           "breakHours": [{"start": "15:00", "end": "17:00"}]}]}]
    assert expand_hours(hours, ["2026-11-21"]) == [
        {"day": "2026-11-21", "start": "10:00", "end": "15:00"},
        {"day": "2026-11-21", "start": "17:00", "end": "21:00"}]


def test_menu_normalization_preserves_missing_and_same_record_evidence():
    from ai.providers.apify import normalize_menu
    menu, evidence = normalize_menu({"name": "한상", "price": "시가"}, "123", 0, "now")
    assert menu["price_krw"] is None and menu["price_text"] == "시가"
    assert evidence["provider_record_id"] == "123" and evidence["mode"] == "live"
    assert evidence["status"] == "missing" and menu["serving_basis"] is None


def test_branch_identity_and_missing_fields():
    from ai.providers.apify import normalize_place
    first = {"place_id": "1", "name": "동명이점", "x": "127.6", "y": "34.7", "address": "여수 A",
             "menus": [{"name": "정식", "price": "10000"}], "businessHours": []}
    other = dict(first, place_id="2", address="여수 B", menus=[])
    a, b = (normalize_place(row, ["2026-11-21"], "now") for row in (first, other))
    assert a["place"]["id"] != b["place"]["id"] and b["menus"] == []
    assert b["opening_hours"]["intervals"] is None
    assert b["evidence"][0]["provider_record_id"] == "2"


def test_cross_provider_match_requires_more_than_name():
    from ai.providers.matching import match_record
    place = {"name": "같은식당", "address": "여수 A", "latitude": 34.7, "longitude": 127.6, "provider_refs": {}}
    wrong = {"place_id": "1", "name": "같은식당", "address": "여수 B", "y": "35.7", "x": "128.6"}
    assert match_record(place, [wrong]) is None
    correct = dict(wrong, place_id="2", address="여수 A", y="34.7", x="127.6")
    assert match_record(place, [wrong, correct])["place_id"] == "2"
    assert match_record(place, [correct, dict(correct, place_id="3")]) is None


async def test_apify_http_caps_five_excludes_reviews_and_keeps_token_out_of_url():
    import httpx
    import json
    from ai.providers.apify import fetch_rows
    def respond(request):
        body = json.loads(request.content)
        assert body["maxItems"] == 5 and body["includeReviews"] is False
        assert "test-secret" not in str(request.url)
        assert request.headers["Authorization"] == "Bearer test-secret"
        return httpx.Response(200, json=[{"place_id": "1"}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        assert await fetch_rows(client, "test-secret", keywords=["여수 맛집"]) == [{"place_id": "1"}]


async def test_probe_missing_credentials_is_not_live_success():
    from ai.providers.probe import probe_place_data
    report = await probe_place_data("apify", "여수", settings={"APIFY_TOKEN": ""})
    assert report["matched_place_count"] == 0 and report["limitations"]
    assert report["mode"] == "live" and report["status"] == "not_run"


def test_menu_identity_survives_reordering_and_zero_text_is_preserved():
    from ai.providers.apify import normalize_menu
    a = {"name": "A", "price": 0}
    b = {"name": "B", "price": 20000}
    first = [normalize_menu(m, "r", i, "now")[0] for i, m in enumerate([a, b])]
    again = [normalize_menu(m, "r", i, "now")[0] for i, m in enumerate([b, a])]
    assert first[0]["id"] == again[1]["id"] and first[1]["id"] == again[0]["id"]
    assert first[0]["price_text"] == "0"


def test_explicit_weekday_closure_is_a_conflict_not_unknown_hours():
    from ai.providers.apify import normalize_place
    from ai.tools.hours import validate_hours
    raw = {"place_id": "r", "name": "closed", "x": "127", "y": "34", "businessHours": [
        {"schedule": [{"day": "수", "start": "", "end": "", "description": "정기휴무"}]}]}
    detail = normalize_place(raw, ["2026-11-18"], "now")
    visit = {"item_id": "i", "date": "2026-11-18", "start_at": "2026-11-18T12:00:00+09:00", "end_at": "2026-11-18T13:00:00+09:00"}
    conflicts, questions = validate_hours(visit, detail, {})
    assert conflicts and not questions


async def test_apify_tourist_probe_caps_two_with_one_per_keyword():
    import httpx, json
    from ai.providers.apify import fetch_rows
    def respond(request):
        body = json.loads(request.content)
        assert body["maxItems"] == 2 and body["maxResultsPerKeyword"] == 1
        return httpx.Response(200, json=[])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await fetch_rows(client, "test", keywords=["관광지1", "관광지2"], limit=2)


def test_same_building_coordinates_do_not_join_different_businesses():
    from ai.providers.matching import match_record
    place = dict(name="식당A", address="전남 여수시 도로1", latitude=34.7, longitude=127.6, provider_refs={})
    wrong = dict(place_id="wrong", name="식당B", roadAddress="전남 여수시 도로1", y="34.7", x="127.6")
    assert match_record(place, [wrong]) is None


def test_matching_road_number_ignores_province_alias_and_building_annotation():
    from ai.providers.matching import match_record
    address = "전남광주통합특별시 여수시 통제영5길 11"
    place = dict(name="서울해장국", address=address, latitude=34.7, longitude=127.6, provider_refs={})
    row = dict(place_id="1", name="서울해장국", roadAddress="전남광주 여수시 통제영5길 11 1층 서울해장국", y="34.7", x="127.6")
    assert match_record(place, [row]) == row and place["address"] == address
    assert match_record(place, [dict(row, roadAddress="전남광주 여수시 통제영5길 12")]) is None
def test_township_road_identity_preserves_optional_eup_myeon():
    from ai.providers.matching import address_key
    assert address_key("전남광주통합특별시 여수시 돌산읍 무술목길 50") == address_key(
        "전남광주 여수시 돌산읍 무술목길 50 모이핀 오션점")
    assert address_key("여수시 돌산읍 무술목길 50") != address_key("여수시 다른면 무술목길 50")


def test_park_parcel_match_tolerates_distinct_representative_points():
    from ai.providers.matching import match_record
    # Recorded Apify/Kakao representative points for 자산공원, ~48 m apart.
    place = dict(name="자산공원", address="전남광주통합특별시 여수시 종화동 3",
                 latitude=34.73948628588617, longitude=127.74980447008349, provider_refs={})
    park = dict(place_id="37609918", name="자산공원", address="전남광주 여수시 종화동 3",
                roadAddress="전남광주 여수시 자산공원길 86", x="127.7503158", y="34.7395995")
    monument = dict(park, place_id="32549377", name="자산공원충혼탑")
    assert match_record(place, [park, monument]) == park
    assert match_record(place, [park, dict(park, place_id="another")]) is None
    assert match_record(place, [dict(park, address="전남광주 여수시 종화동 3-1")]) is None


def test_matching_does_not_merge_similar_road_numbers_in_different_provinces():
    from ai.providers.matching import match_record
    place = dict(name="중앙식당", address="강원특별자치도 고성군 중앙로 12",
                 latitude=34.7, longitude=127.6, provider_refs={})
    row = dict(place_id="1", name="중앙식당", roadAddress="경남 고성군 중앙로 12", x="127.6", y="34.7")
    assert match_record(place, [row]) is None


def test_missing_township_annotation_can_match_but_conflicting_townships_cannot():
    from ai.providers.matching import match_record
    place = dict(name="가게", address="전남 여수시 중앙길 12", latitude=34.7, longitude=127.6, provider_refs={})
    row = dict(place_id="1", name="가게", roadAddress="전남 여수시 돌산읍 중앙길 12", x="127.6", y="34.7")
    assert match_record(place, [row]) == row
    assert match_record(dict(place, address="전남 여수시 화양면 중앙길 12"), [row]) is None


def test_no_regular_closure_and_overnight_provider_hours():
    from ai.providers.hours import closed_dates, expand_hours
    hours = [{"schedule": [{"day": "매일", "start": "20:00", "end": "02:00",
                            "description": "정기휴무 없음"}]}]
    assert closed_dates(hours, ["2026-11-21"]) == []
    assert expand_hours(hours, ["2026-11-21"]) == [
        {"day": "2026-11-21", "start": "00:00", "end": "02:00"},
        {"day": "2026-11-21", "start": "20:00", "end": "24:00"},
        {"day": "2026-11-22", "start": "00:00", "end": "02:00"}]
    assert expand_hours([{"schedule": [{"day": "매일", "start": "00:00", "end": "00:00"}]}],
                        ["2026-11-21"]) == []
