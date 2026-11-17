async def search_places(client, key, query, region):
    if not key:
        raise ValueError("KAKAO_REST_API_KEY missing")
    response = await client.get("https://dapi.kakao.com/v2/local/search/keyword.json",
        headers={"Authorization": "KakaoAK " + key}, params={"query": query if region in query else region + " " + query, "size": 5})
    response.raise_for_status()
    return {"places": [dict(id="kakao:" + row["id"], name=row["place_name"],
                           address=row.get("road_address_name") or row["address_name"],
                           latitude=float(row["y"]), longitude=float(row["x"]), provider_refs={"kakao": row["id"]})
                       for row in response.json()["documents"]]}
