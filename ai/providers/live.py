from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import httpx

from ai.providers.apify import fetch_rows, missing_fields, normalize_hours, normalize_place
from ai.providers.kakao import search_places, get_car_route
from ai.providers.matching import record_match
from ai.tools.routes import aware_datetime, observed_route


PLACE_DETAILS_MAX_AGE = timedelta(days=1)


def trip_days(config):
    try:
        first, last = (date.fromisoformat(config.get(k)) for k in ("start_date", "end_date"))
    except (TypeError, ValueError):
        return []
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def detail_matches_place(detail, place):
    saved = detail["place"]
    return all(saved.get(k) == place.get(k) for k in ("id", "name", "address", "latitude", "longitude")) and all(
        saved.get("provider_refs", {}).get(provider) == ref for provider, ref in place.get("provider_refs", {}).items())


def current_place_details(detail, place, config, mode):
    evidence = detail.get("evidence", [])
    if detail.get("match_status", "matched") != "matched" or not detail_matches_place(detail, place):
        return None
    if not evidence or not all(e.get("mode") == "live" for e in evidence):
        return detail if mode != "live" else None
    now = datetime.now(timezone.utc)
    if any(not timestamp or not timedelta() <= now - timestamp <= PLACE_DETAILS_MAX_AGE
           for timestamp in (aware_datetime(e.get("retrieved_at")) for e in evidence)):
        return None
    if any(e.get("match_status") != "matched" for e in evidence):
        return None
    hours = next((e for e in evidence if e.get("field") == "opening_hours" and e.get("provider") == "apify"), None)
    if hours is None or not isinstance(hours.get("raw_value"), list):
        return None
    days = trip_days(config)
    detail = deepcopy(detail)
    hours = next(e for e in detail["evidence"] if e["id"] == hours["id"])
    detail["opening_hours"], normalized = normalize_hours(hours["raw_value"], days, hours["id"])
    hours.update(normalized_value=normalized, status="missing" if normalized is None else "api_observed")
    detail.update(match_status="matched", missing_fields=missing_fields(detail.get("menus", []), detail["opening_hours"], days))
    return detail


def recent_detail_attempt(detail, place):
    retrieved = aware_datetime(detail.get("retrieved_at"))
    return bool(detail.get("match_status") in ("ambiguous", "unmatched") and retrieved
                and timedelta() <= datetime.now(timezone.utc) - retrieved <= PLACE_DETAILS_MAX_AGE
                and detail_matches_place(detail, place))


def cached_result(name, arguments, context):
    if name == "get_place_details":
        ref = arguments["place_ref"]
        cached = context["details"].get(ref)
        if cached and not ref.startswith("fixture:"):
            return current_place_details(cached, context["places"][ref], context["config"], "live")
    if name == "get_car_route":
        try:
            return observed_route(context, arguments)
        except ValueError:
            pass
    return None


async def execute(name, arguments, context, settings):
    if any(str(arguments.get(k, "")).startswith("fixture:") for k in ("place_ref", "from_ref", "to_ref")):
        raise ValueError("Fixture reference cannot be used in live mode")
    async with httpx.AsyncClient(timeout=30) as client:
        if name == "search_places":
            return await search_places(client, settings.get("KAKAO_REST_API_KEY", ""), arguments["query"], arguments["region"])
        if name == "get_car_route":
            return await get_car_route(client, settings.get("KAKAO_MOBILITY_API_KEY") or settings.get("KAKAO_REST_API_KEY"),
                                       context["places"], arguments)
        return await get_place_details(client, settings, context["places"][arguments["place_ref"]], trip_days(context["config"]))


async def get_place_details(client, settings, place, days):
    record = place.get("provider_refs", {}).get("apify")
    selection = {"urls": ["https://map.naver.com/p/entry/place/" + str(record)]} if record else {
        "keywords": [place["name"] + " " + place["address"]]}
    rows = await fetch_rows(client, settings.get("APIFY_TOKEN", ""), **selection)
    status, matched = record_match(place, rows)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    if matched is None:
        return dict(place=deepcopy(place), menus=[], opening_hours=None, evidence=[], match_status=status,
                    missing_fields=["details", "price", "opening_hours"], retrieved_at=retrieved_at)
    return normalize_place(matched, days, retrieved_at, lookup_place=place)
