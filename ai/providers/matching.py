import re


def address_key(address):
    road = re.search(r"([가-힣]+(?:시|군|구))\s+(?:([가-힣]+(?:읍|면))\s+)?([가-힣0-9·.]+(?:로|길))\s*(\d+(?:-\d+)?)", address)
    return road.groups() if road else address.replace(" ", "")


def match_record(place, rows):
    known = place.get("provider_refs", {}).get("apify")
    matches = []
    for row in rows:
        address = row.get("roadAddress") or row.get("address") or ""
        same_address = bool(address) and address_key(address) == address_key(place["address"])
        nearby = abs(float(row.get("y") or 0) - place["latitude"]) < .0003 and abs(float(row.get("x") or 0) - place["longitude"]) < .0003
        same_name = row.get("name", "").replace(" ", "") == place["name"].replace(" ", "")
        if (known and str(row["place_id"]) == known) or (not known and same_name and same_address and nearby):
            matches.append(row)
    return matches[0] if len(matches) == 1 else None
