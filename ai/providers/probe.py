"""Probe reports exclude fixtures, uncertain branches and missing values."""
from datetime import datetime, timezone
import httpx
from ai.providers.apify import fetch_rows, normalize_place
from ai.settings import load_settings
import argparse
import asyncio
import json
from pathlib import Path


async def main(args):
    report = await probe_place_data(args.provider, args.region,
                                    load_settings({"env_file": args.env_file}), args.dates)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "details"}, ensure_ascii=True))


async def probe_place_data(provider, region, settings=None, days=None):
    settings = settings if settings is not None else load_settings({})
    report = summarize(provider, region, [])
    if provider != "apify" or not settings.get("APIFY_TOKEN"):
        return dict(report, status="not_run", limitations=["Selected provider credential/adapter unavailable"])
    async with httpx.AsyncClient() as client:
        raw = await fetch_rows(client, settings["APIFY_TOKEN"], keywords=[region + " 맛집"])
    stamp = datetime.now(timezone.utc).isoformat()
    details = [normalize_place(r, days or [], stamp) for r in raw]
    rows = [dict(region=region if region in d["place"]["address"] else "", mode="live", match_status="matched",
                 price_krw=next((m["price_krw"] for m in d["menus"] if m["price_krw"] is not None), None),
                 intervals=d["opening_hours"]["intervals"]) for d in details]
    return dict(summarize(provider, region, rows), status="observed", details=details,
                limitations=["Serving quantities and provider update dates may be unknown; tourist coverage separate"])


def summarize(provider, region, rows):
    valid = [r for r in rows if r.get("region") == region and r.get("mode") == "live"
             and r.get("match_status") == "matched"]
    return dict(provider=provider, mode="live", region=region,
                matched_place_count=len(valid),
                priced_menu_count=sum(r.get("price_krw") is not None for r in valid),
                usable_hours_count=sum(bool(r.get("intervals")) for r in valid),
                source_refs=[], limitations=[])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--dates", nargs="*", default=[])
    asyncio.run(main(parser.parse_args()))
