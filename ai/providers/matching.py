def match_record(place, rows):
    known = place.get("provider_refs", {}).get("apify")
    matches = []
    for row in rows:
        address = row.get("roadAddress") or row.get("address") or ""
        same_address = bool(address) and address.replace(" ", "") == place["address"].replace(" ", "")
        nearby = abs(float(row.get("y") or 0) - place["latitude"]) < .0003 and abs(float(row.get("x") or 0) - place["longitude"]) < .0003
        if (known and str(row["place_id"]) == known) or (not known and same_address and nearby):
            matches.append(row)
    return matches[0] if len(matches) == 1 else None
