from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json


async def get_car_route(client, key, places, arguments):
    if not key:
        raise ValueError("KAKAO_MOBILITY_API_KEY missing")
    params = {key: f"{places[arguments[ref]]['longitude']},{places[arguments[ref]]['latitude']}"
              for key, ref in (("origin", "from_ref"), ("destination", "to_ref"))}
    path = "/v1/directions"
    if arguments.get("departure_at"):
        departure = datetime.fromisoformat(arguments["departure_at"])
        if departure.tzinfo is None or departure <= datetime.now(timezone.utc):
            raise ValueError("Departure must be timezone-aware and in the future")
        path = "/v1/future/directions"
        params["departure_time"] = departure.astimezone(timezone(timedelta(hours=9))).strftime("%Y%m%d%H%M")
    response = await client.get("https://apis-navi.kakaomobility.com" + path,
                                headers={"Authorization": "KakaoAK " + key}, params=params)
    response.raise_for_status()
    route = response.json()["routes"][0]
    if route["result_code"] != 0:
        raise ValueError("Driving route unavailable")
    summary = route["summary"]
    vertices = [road["vertexes"] for section in route.get("sections", []) for road in section.get("roads", [])]
    polyline = [dict(latitude=points[i + 1], longitude=points[i]) for points in vertices for i in range(0, len(points), 2)]
    ref = sha256(json.dumps([arguments, params], sort_keys=True).encode()).hexdigest()[:20]
    return dict(from_ref=arguments["from_ref"], to_ref=arguments["to_ref"],
                distance_m=summary["distance"], duration_seconds=summary["duration"],
                toll_krw=summary.get("fare", {}).get("toll"), polyline=polyline, evidence_id="kakao:route:" + ref)


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
