import httpx


async def test_live_details_keep_original_ref_and_provider_record_identity():
    from ai.providers.live import get_place_details
    place = dict(id="kakao:1", name="A", address="여수 A", latitude=34.7, longitude=127.6,
                 provider_refs={"kakao": "1", "apify": "99"})
    def respond(request):
        return httpx.Response(200, json=[dict(place_id="99", name="A", address="여수 A", y="34.7", x="127.6", menus=[])])
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await get_place_details(client, {"APIFY_TOKEN": "test"}, place, ["2026-11-21"])
    assert result["place"]["id"] == "kakao:1"
    assert result["place"]["provider_refs"] == {"kakao": "1", "apify": "99"}
    assert result["evidence"][0]["mode"] == "live"


async def test_trusted_provider_id_supplies_details_without_replacing_lookup_coordinates():
    from ai.providers.live import get_place_details
    place = dict(id="kakao:1", name="A", address="여수 A", latitude=34.7, longitude=127.6,
                 provider_refs={"kakao": "1", "apify": "99"})
    rows = [dict(place_id="99", name="A", menus=[dict(name="식사", price="10000")]),
            dict(place_id="11", name="A", y="34.7", x="127.6", address="여수 A", menus=[])]
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=rows))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_place_details(client, {"APIFY_TOKEN": "test"}, place, ["2026-11-21"])
    assert result["place"] == place and result["menus"][0]["price_krw"] == 10000
    assert result["evidence"][0]["provider_record_id"] == "99"


async def test_live_ambiguous_source_preserves_evidenced_place_and_never_picks_a_branch():
    from ai.providers.live import get_place_details
    from ai.tools.context import build_tool_context
    place = dict(id="kakao:1", name="가게", address="전남 여수시 중앙로 11", latitude=34.7, longitude=127.6,
                 provider_refs={"kakao": "1"})
    candidate = dict(place_id="11", name="가게", roadAddress=place["address"], y="34.7", x="127.6")
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=[candidate, dict(candidate, place_id="12")]))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await get_place_details(client, {"APIFY_TOKEN": "test"}, place, ["2026-11-21"])
    assert result["place"] == place and result["match_status"] == "ambiguous"
    assert result["menus"] == [] and result["opening_hours"] is None and result["evidence"] == []
    assert set(result["missing_fields"]) == {"details", "price", "opening_hours"}
    observation = dict(tool_name="get_place_details", arguments=dict(place_ref=place["id"]), result=result)
    context = build_tool_context(dict(config={}, observations=[observation], _provider_mode="live"))
    assert place["id"] in context["detail_attempts"] and place["id"] not in context["details"]


async def test_fixture_evidence_is_not_reused_as_live_details(monkeypatch):
    import pytest
    from ai.tools.registry import RegisteredTools
    from ai.tests.test_place_route_tools import task
    value = task()
    with pytest.raises(ValueError):
        await RegisteredTools(value, "live", {}).execute("get_place_details", {"place_ref": "fixture:place-a"})


async def test_detail_cache_reuses_raw_hours_for_new_dates_and_tracks_real_source(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from ai.providers.apify import normalize_place
    from ai.tools.registry import RegisteredTools

    now = datetime.now(timezone.utc)
    raw = dict(place_id="99", name="A", roadAddress="여수 A", y="34.7", x="127.6",
               businessHours=[dict(schedule=[dict(day="매일", start="10:00", end="20:00")])])
    cached = normalize_place(raw, ["2026-11-21"], now.isoformat())
    place, ref = cached["place"], cached["place"]["id"]
    context = dict(config=dict(start_date="2026-11-22", end_date="2026-11-22"), observations=[
        dict(tool_name="search_places", arguments={}, result=dict(places=[place])),
        dict(tool_name="get_place_details", arguments=dict(place_ref=ref), result=cached)])

    async def external_details(client, settings, place, days):
        return normalize_place(raw, days, now.isoformat())

    monkeypatch.setattr("ai.providers.live.get_place_details", external_details)
    tools = RegisteredTools(context, "live", {})
    result = await tools.execute("get_place_details", dict(place_ref=ref))
    assert result["opening_hours"]["intervals"] == [dict(day="2026-11-22", start="10:00", end="20:00")]
    assert result["evidence"][0]["retrieved_at"] == now.isoformat() and tools.last_execution_source == "cache"

    cached["evidence"][0]["retrieved_at"] = (now - timedelta(days=2)).isoformat()
    tools.restore(context)
    result = await tools.execute("get_place_details", dict(place_ref=ref))
    assert result["evidence"][0]["retrieved_at"] == now.isoformat() and tools.last_execution_source == "http"

    cached["evidence"][0]["retrieved_at"] = now.isoformat()
    context["observations"].append(dict(tool_name="search_places", arguments={},
                                       result=dict(places=[dict(place, latitude=35)])))
    tools.restore(context)
    await tools.execute("get_place_details", dict(place_ref=ref))
    assert tools.last_execution_source == "http"


def test_current_driving_cache_expires_and_cannot_supply_future_trip():
    from datetime import datetime, timedelta, timezone
    import pytest
    from ai.providers.kakao import route_evidence_id
    from ai.tools.routes import observed_route

    now = datetime.now(timezone.utc)
    arguments = dict(from_ref="a", to_ref="b", departure_at=None)
    places = {"a": dict(latitude=34.7, longitude=127.6), "b": dict(latitude=34.8, longitude=127.8)}
    leg = dict(from_ref="a", to_ref="b", duration_seconds=600, evidence_id=route_evidence_id(places, arguments),
               retrieved_at=(now - timedelta(minutes=20)).isoformat())
    observation = dict(tool_name="get_car_route", arguments=arguments, result=leg, observed_at=now.isoformat())
    context = dict(places=places, observations=[observation], _provider_mode="live")
    with pytest.raises(ValueError):
        observed_route(context, arguments)
    leg["retrieved_at"] = now.isoformat()
    assert observed_route(context, arguments)["duration_seconds"] == 600
    with pytest.raises(ValueError):
        observed_route(context, dict(arguments, departure_at=(now + timedelta(days=1)).isoformat()))
