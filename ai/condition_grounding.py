"""Conservative, source-grounded normalization for supported personal conditions."""
import re
from decimal import Decimal


def condition_value(key, text):
    if re.search(r'아니(?:야|고|라|에|면|다)|아냐|아닌|아닙|않|모르|취소|철회|말고|만약|이면|라면|어때|[?？]|전체|총예산|공동|라고|했대|말했|보다|정도|쯤|안\s*(?:해|하|돼|되)|필요\s*없', text):
        return None
    if key in ('budget', 'budget_krw'):
        if len(re.findall(r'\d+(?:\.\d+)?\s*(?:만\s*원|원)', text)) != 1:
            return None
        match = re.search(r'(?:^|[.!;\n]\s*)(?:(?:아니|나는|난|저는|내|제|나의|저의)\s*)*(?:개인|1인당)?\s*예산.{0,10}?(\d+(?:\.\d+)?)\s*(만\s*원|원)', text)
        if match:
            return int(Decimal(match[1]) * (10000 if '만' in match[2] else 1))
    if key == "return_by" and any(word in text for word in ("도착", "귀가", "돌아")):
        match = re.search(r"(?:^|[.!;\n]\s*)(?:(?:나는|난|저는|내가)\s*)?(?:오전|오후)?\s*(\d{1,2})(?::(\d{2}))?\s*시?\s*까지", text)
        if match and int(match[1]) < 24 and int(match[2] or 0) < 60:
            hour = int(match[1])
            if "오후" in text and hour < 12:
                hour += 12
            if "오전" in text and hour == 12:
                hour = 0
            return f"{hour:02}:{int(match[2] or 0):02}"
    return None
