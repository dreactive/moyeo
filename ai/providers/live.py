from datetime import datetime, timezone
from ai.providers.apify import fetch_rows, normalize_place
from ai.providers.matching import match_record


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
