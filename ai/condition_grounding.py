"""Conservative normalization of complete, explicit personal assertions."""
import re
from decimal import Decimal

START = r'(?:^|[.!;\n]\s*)'
END = r'\s*(?=[.!;\n]|$)'
PERSONAL = r'(?:(?:아니|나는|난|저는|내|제|나의|저의|내가)\s*)*'
AMOUNT = r'(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)'
BUDGET = START + PERSONAL + r'(?:개인|1인당)?\s*예산(?:은|는|이|을)?\s*' + AMOUNT + r'\s*(만\s*원|원)(?:이야|야|이에요|예요|입니다|으로\s*(?:할게|정정할게|정정합니다))?' + END
DEADLINE = START + PERSONAL + r'(오전|오후)?\s*(\d{1,2})(?::(\d{2}))?\s*시?\s*까지\s*(?:[^\s.?!;]+(?:에|으로)\s*)?(?:귀가|도착)(?:해야\s*(?:해요|해|돼요|돼|합니다)|하겠습니다|할게요|할게)?' + END
CLAUSE_BREAK = r'[!?？;\n]|(?<!\d)\.|\.(?!\d)'
NON_ASSERTION = re.compile(r'아니(?:야|고|라|에|면|다)|아냐|아닌|아닙|않|모르|취소|철회|말고|만약|이면|라면|어때|전체|총\s*예산|공동|라고|했대|말했|보다|정도|쯤|안\s*(?:해|하|돼|되)|필요\s*없')


def budget_value(text):
    matches = list(re.finditer(BUDGET, text))
    if len(matches) != 1:
        return None
    amount, unit = matches[0].groups()
    value = Decimal(amount.replace(',', '')) * (10000 if '만' in unit else 1)
    return int(value) if value == value.to_integral_value() else None


def deadline_value(text):
    matches = list(re.finditer(DEADLINE, text))
    if len(matches) != 1:
        return None
    period, hour, minute = matches[0].groups()
    hour, minute = int(hour), int(minute or 0)
    if hour > 23 or minute > 59 or period and not 1 <= hour <= 12:
        return None
    hour = hour % 12 + (12 if period == '오후' else 0) if period else hour
    return f'{hour:02}:{minute:02}'


def condition_value(key, text):
    budget = key in ('budget', 'budget_krw')
    if not budget and key != 'return_by' or re.search(r'["“”‘’`]', text):
        return None
    parser, topic = (budget_value, r'예산') if budget else (deadline_value, r'귀가|도착')
    parts = re.split('(' + CLAUSE_BREAK + ')', text)
    values = []
    for index in range(0, len(parts), 2):
        clause = parts[index].strip()
        if not re.search(topic, clause):
            continue
        if NON_ASSERTION.search(clause) or index + 1 < len(parts) and parts[index + 1] in ('?', '？'):
            return None
        value = parser(clause)
        if value is not None:
            values.append(value)
    return values[0] if len(values) == 1 else None
