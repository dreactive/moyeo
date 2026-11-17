from ai.providers.normalize import price_krw
from ai.providers.hours import expand_hours
import json


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
                   holiday_text=json.dumps([{k: h.get(k) for k in ("comingRegularClosedDays", "comingIrregularClosedDays")}
                                            for h in hours], ensure_ascii=False), evidence_id=ref)
    return dict(place=place, menus=[p[0] for p in pairs], opening_hours=opening,
                evidence=[p[1] for p in pairs] + [evidence(record_id, "opening_hours", hours, intervals, retrieved_at, ref)])


def evidence(record_id, field, raw, normalized, retrieved_at, evidence_id):
    return dict(id=evidence_id, provider="apify", provider_record_id=record_id,
                source_url="https://map.naver.com/p/entry/place/" + record_id,
                field=field, raw_value=raw, normalized_value=normalized,
                status="missing" if normalized is None else "api_observed",
                retrieved_at=retrieved_at, provider_updated_at=None, mode="live", match_status="matched")


def normalize_menu(raw, record_id, index, retrieved_at):
    ref = f"apify:{record_id}:menu:{index}"
    price = price_krw(raw.get("price"))
    menu = dict(id=ref, name=raw["name"], price_krw=price,
                price_text=str(raw.get("priceText") or raw.get("price") or ""),
                serving_basis=raw.get("servingBasis"), evidence_id=ref + ":price")
    return menu, evidence(record_id, "menu_price", raw.get("price"), price, retrieved_at, ref + ":price")
