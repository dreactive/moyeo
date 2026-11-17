import re


def price_krw(value):
    text = str("" if value is None else value).strip().replace(",", "").removesuffix("원").strip()
    return int(text) if re.fullmatch(r"[0-9]+", text) else None
