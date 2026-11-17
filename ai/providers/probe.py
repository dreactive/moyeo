"""Probe reports exclude fixtures, uncertain branches and missing values."""


def summarize(provider, region, rows):
    valid = [r for r in rows if r.get("region") == region and r.get("mode") == "live"
             and r.get("match_status") == "matched"]
    return dict(provider=provider, mode="live", region=region,
                matched_place_count=len(valid),
                priced_menu_count=sum(r.get("price_krw") is not None for r in valid),
                usable_hours_count=sum(bool(r.get("intervals")) for r in valid),
                source_refs=[], limitations=[])
