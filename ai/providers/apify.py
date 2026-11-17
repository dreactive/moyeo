from ai.providers.normalize import price_krw


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
