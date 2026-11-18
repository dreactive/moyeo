import math
import re
import unicodedata


_PROVINCES = {
    "서울": ("서울특별시",), "부산": ("부산광역시",), "대구": ("대구광역시",),
    "인천": ("인천광역시",), "광주": ("광주광역시",), "대전": ("대전광역시",),
    "울산": ("울산광역시",), "세종": ("세종특별자치시",), "경기": ("경기도",),
    "강원": ("강원도", "강원특별자치도"), "충북": ("충청북도",), "충남": ("충청남도",),
    "전북": ("전라북도", "전북특별자치도"),
    "전남": ("전라남도", "전남광주", "전남광주통합특별시"), "경북": ("경상북도",),
    "경남": ("경상남도",), "제주": ("제주도", "제주특별자치도"),
}
_PROVINCE_KEY = {alias: key for key, aliases in _PROVINCES.items() for alias in (key, *aliases)}
_NUMBERED_ADDRESS = re.compile(
    r"^(?P<region>(?:[가-힣]+(?:시|군|구|읍|면)\s+)*)"
    r"(?P<street>[가-힣0-9·.]+(?:로|길|동|가|리))\s*(?P<mountain>산\s*)?"
    r"(?P<number>\d+(?:-\d+)?)(?=$|\s|\(|,)"
)


def address_key(address):
    address = unicodedata.normalize("NFKC", address or "").strip()
    first, _, rest = address.partition(" ")
    province = _PROVINCE_KEY.get(first)
    numbered = _NUMBERED_ADDRESS.match(rest.lstrip() if province else address)
    if numbered and (numbered["region"] or province):
        kind = "road" if numbered["street"].endswith(("로", "길")) else "parcel"
        return kind, province, tuple(numbered["region"].split()), numbered["street"], bool(numbered["mountain"]), numbered["number"]
    return "text", "".join(address.split())


def _same_address(left, right):
    if left == right:
        return True
    if left[0] == "text" or left[3:] != right[3:] or (left[1] and right[1] and left[1] != right[1]):
        return False
    shorter, longer = sorted((left[2], right[2]), key=len)
    return (bool(shorter or left[1] == right[1]) and longer[:len(shorter)] == shorter
            and all(part.endswith(("읍", "면")) for part in longer[len(shorter):]))


def _address_matches(place, row):
    places = {address_key(place[key]) for key in ("address", "road_address", "parcel_address") if place.get(key)}
    records = {address_key(row[key]) for key in ("roadAddress", "address") if row.get(key)}
    matched = set()
    for kind in ("road", "parcel", "text"):
        left = [key for key in places if key[0] == kind]
        right = [key for key in records if key[0] == kind]
        if not left or not right:
            continue
        if any(_same_address(a, b) for a in left for b in right):
            matched.add(kind)
        elif kind != "text":
            return set()  # A shared parcel cannot override a different street address.
    return matched


def _nearby(place, row, matched):
    try:
        y, x = float(row["y"]), float(row["x"])
        latitude, longitude = place["latitude"], place["longitude"]
        dy = (y - latitude) * 111_200
        dx = (x - longitude) * 111_200 * math.cos(math.radians(latitude))
    except (KeyError, TypeError, ValueError):
        return False
    # Parks and other campus-like POIs may be pinned at an entrance or centroid.
    large_place = re.search(r"(?:공원|수목원|유원지|해수욕장|섬|캠퍼스)$", place["name"])
    return math.hypot(dx, dy) <= (150 if large_place and matched & {"parcel", "road"} else 40)


def record_match(place, rows):
    known = place.get("provider_refs", {}).get("apify")
    if known:
        matches = [row for row in rows if row.get("place_id") is not None and str(row["place_id"]) == str(known)]
    else:
        name = "".join(unicodedata.normalize("NFKC", place["name"]).casefold().split())
        matches = []
        for row in rows:
            if not row.get("place_id") or "".join(unicodedata.normalize("NFKC", row.get("name") or "").casefold().split()) != name:
                continue
            matched = _address_matches(place, row)
            if matched and _nearby(place, row, matched):
                matches.append(row)
    if len(matches) == 1:
        return "matched", matches[0]
    return ("ambiguous" if matches else "unmatched"), None


def match_record(place, rows):
    return record_match(place, rows)[1]
