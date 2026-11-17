"""Standalone boundary replay, never a substitute for Backend confirmations."""


def read_path(value, path):
    for part in path.split("."):
        try:
            if isinstance(value, list):
                value = len(value) if part == "length" else value[int(part)]
            else:
                value = value.get(part)
        except (IndexError, ValueError, TypeError, AttributeError):
            return None
    return value
