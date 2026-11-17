import os
from pathlib import Path

KEYS = ("KAKAO_REST_API_KEY", "KAKAO_MOBILITY_API_KEY", "APIFY_TOKEN", "JEONNAM_API_KEY",
        "TOURAPI_SERVICE_KEY", "ODCLOUD_SERVICE_KEY", "PLACE_DETAILS_PROVIDER")


def load_settings(config):
    values = {k: os.environ.get(k, "") for k in KEYS}
    path = Path(config.get("env_file") or "")
    if path.is_file():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.removeprefix("export ").partition("=")
            if separator and key.strip() in KEYS:
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values
