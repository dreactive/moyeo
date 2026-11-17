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
