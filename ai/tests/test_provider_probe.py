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
