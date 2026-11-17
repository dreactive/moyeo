from datetime import datetime, timezone
from ai.providers.apify import fetch_rows, normalize_place
from ai.providers.matching import match_record
from datetime import date, timedelta
from copy import deepcopy
import httpx
from ai.providers.kakao import search_places, get_car_route
from ai.tools.routes import observed_route


async def execute(name, arguments, context, settings):
    if any(str(arguments.get(k, "")).startswith("fixture:") for k in ("place_ref", "from_ref", "to_ref")):
        raise ValueError("Fixture reference cannot be used in live mode")
    if name == "get_place_details":
        cached = context["details"].get(arguments["place_ref"])
        if cached and cached["evidence"] and all(e["mode"] == "live" for e in cached["evidence"]):
            return deepcopy(cached)
    if name == "get_car_route":
        try:
            cached = observed_route(context, arguments)
            if cached["evidence_id"].startswith("kakao:route:"):
                return cached
        except ValueError:
            pass
    async with httpx.AsyncClient(timeout=30) as client:
        if name == "search_places":
            return await search_places(client, settings.get("KAKAO_REST_API_KEY", ""), arguments["query"], arguments["region"])
        if name == "get_car_route":
            return await get_car_route(client, settings.get("KAKAO_MOBILITY_API_KEY") or settings.get("KAKAO_REST_API_KEY"),
                                       context["places"], arguments)
        config = context["config"]
        first, last = (date.fromisoformat(config[k]) for k in ("start_date", "end_date"))
        days = [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]
        return await get_place_details(client, settings, context["places"][arguments["place_ref"]], days)


async def get_place_details(client, settings, place, days):
    record = place.get("provider_refs", {}).get("apify")
    selection = {"urls": ["https://map.naver.com/p/entry/place/" + record]} if record else {
        "keywords": [place["name"] + " " + place["address"]]}
    rows = await fetch_rows(client, settings.get("APIFY_TOKEN", ""), **selection)
    matched = match_record(place, rows)
    if matched is None:
        raise ValueError("Same branch could not be uniquely matched; choose a place")
    detail = normalize_place(matched, days, datetime.now(timezone.utc).isoformat())
    detail["place"]["id"] = place["id"]
    detail["place"]["provider_refs"].update(place["provider_refs"])
    return detail
