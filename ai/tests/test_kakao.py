import httpx


async def test_search_maps_provider_ids_and_coordinates():
    from ai.providers.kakao import search_places
    def respond(request):
        assert request.url.params["query"] == "여수 역"
        assert request.headers["Authorization"] == "KakaoAK test"
        return httpx.Response(200, json={"documents": [{"id": "1", "place_name": "역",
            "road_address_name": "여수 A", "address_name": "A", "x": "127.6", "y": "34.7"}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await search_places(client, "test", "역", "여수")
    assert result["places"][0]["id"] == "kakao:1" and result["places"][0]["latitude"] == 34.7


async def test_future_route_uses_requested_time_and_preserves_units():
    from ai.providers.kakao import get_car_route
    def respond(request):
        assert request.url.path == "/v1/future/directions"
        assert request.url.params["departure_time"] == "209901210900"
        return httpx.Response(200, json={"routes": [{"result_code": 0,
            "summary": {"distance": 3568, "duration": 459, "fare": {"toll": 0}}, "sections": []}]})
    arguments = dict(from_ref="anchor:origin", to_ref="p", departure_at="2099-01-21T09:00:00+09:00")
    places = {"anchor:origin": {"latitude": 34.7, "longitude": 127.6}, "p": {"latitude": 34.8, "longitude": 127.7}}
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await get_car_route(client, "test", places, arguments)
    assert (result["distance_m"], result["duration_seconds"], result["toll_krw"]) == (3568, 459, 0)
