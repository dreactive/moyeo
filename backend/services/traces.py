import re

PRIVATE = re.compile(r'key|token|password|secret|authorization|reasoning|thought|raw_response', re.I)
URL_SECRET = re.compile(r'([?&](?:api_?key|token|servicekey)=)[^&\s]+', re.I)


def sanitize(value):
    if isinstance(value, dict):
        return {key:sanitize(item) for key,item in value.items() if not PRIVATE.search(key)}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        return URL_SECRET.sub(r'\1[redacted]', value)
    return value
