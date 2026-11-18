"""Conservative, source-grounded normalization for supported personal conditions."""
import re


def condition_value(key, text):
    if key in ('budget', 'budget_krw'):
        match = re.search(r'예산.{0,10}?(\d+)\s*(만\s*원|원)', text)
        if match:
            return int(match[1]) * (10000 if '만' in match[2] else 1)
    return None
