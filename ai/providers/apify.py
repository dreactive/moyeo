from ai.providers.normalize import price_krw
from ai.providers.hours import expand_hours, closed_dates
import json
from hashlib import sha256


async def fetch_rows(client, token, *, keywords=None, urls=None, limit=5):
    if not token:
        raise ValueError("APIFY_TOKEN missing")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 5:
        raise ValueError("Apify sample limit must be 1..5")
    body = dict(maxResults=1 if len(keywords or []) > 1 else limit, maxItems=limit,
                includeDetails=True, includeReviews=False)
    body.update({"urls": urls[:5]} if urls else {"searchKeywords": (keywords or [])[:5]})
    response = await client.post("https://api.apify.com/v2/acts/huggable_quote~naver-map-scraper/run-sync-get-dataset-items",
                                 headers={"Authorization": "Bearer " + token},
                                 params={"timeout": 180}, json=body, timeout=210)
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError("Apify did not return dataset rows")
    return rows[:5]


def normalize_place(raw, days, retrieved_at):
    record_id = str(raw["place_id"])
    place = dict(id="apify:" + record_id, name=raw["name"],
                 address=raw.get("roadAddress") or raw.get("address") or "",
                 latitude=float(raw["y"]), longitude=float(raw["x"]), provider_refs={"apify": record_id})
    pairs = [normalize_menu(m, record_id, i, retrieved_at) for i, m in enumerate(raw.get("menus") or [])]
    hours = raw.get("businessHours") or []
    intervals = expand_hours(hours, days) or None
    ref = "apify:" + record_id + ":hours"
    opening = dict(raw_text=json.dumps(hours, ensure_ascii=False), intervals=intervals,
                   holiday_text=json.dumps(dict(closed_dates=closed_dates(hours, days),
                       descriptions=[s.get("description") for h in hours for s in h.get("schedule") or []]),
                       ensure_ascii=False), evidence_id=ref)
    return dict(place=place, menus=[p[0] for p in pairs], opening_hours=opening,
                evidence=[p[1] for p in pairs] + [evidence(record_id, "opening_hours", hours, intervals, retrieved_at, ref)])


def evidence(record_id, field, raw, normalized, retrieved_at, evidence_id):
    return dict(id=evidence_id, provider="apify", provider_record_id=record_id,
                source_url="https://map.naver.com/p/entry/place/" + record_id,
                field=field, raw_value=raw, normalized_value=normalized,
                status="missing" if normalized is None else "api_observed",
                retrieved_at=retrieved_at, provider_updated_at=None, mode="live", match_status="matched")


def normalize_menu(raw, record_id, index, retrieved_at):
    signature = json.dumps([raw["name"], raw.get("servingBasis"), raw.get("description")], ensure_ascii=False)
    stable_id = str(raw.get("menuId") or sha256(signature.encode()).hexdigest()[:16])
    ref = f"apify:{record_id}:menu:{stable_id}"
    price = price_krw(raw.get("price"))
    text = raw.get("priceText") if raw.get("priceText") is not None else raw.get("price")
    menu = dict(id=ref, name=raw["name"], price_krw=price,
                price_text=str("" if text is None else text),
                serving_basis=raw.get("servingBasis"), evidence_id=ref + ":price")
    return menu, evidence(record_id, "menu_price", raw.get("price"), price, retrieved_at, ref + ":price")
