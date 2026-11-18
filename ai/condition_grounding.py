"""Conservative, source-grounded normalization for supported personal conditions."""
import re


def condition_value(key, text):
    if key in ('budget', 'budget_krw'):
        match = re.search(r'예산.{0,10}?(\d+)\s*(만\s*원|원)', text)
        if match:
            return int(match[1]) * (10000 if '만' in match[2] else 1)
    if key == "return_by" and any(word in text for word in ("도착", "귀가", "돌아")):
        match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*시?\s*까지", text)
        if match and int(match[1]) < 24 and int(match[2] or 0) < 60:
            return f"{int(match[1]):02}:{int(match[2] or 0):02}"
    return None
