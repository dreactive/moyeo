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
