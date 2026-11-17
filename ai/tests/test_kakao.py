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
