from datetime import datetime, timedelta, timezone


def agent_config(config):
    """Complete optional dates in a tool/agent copy, preserving saved settings."""
    config = dict(config)
    start, end = config.get('start_date'), config.get('end_date')
    if not start or not end:
        day = start or end or datetime.now(timezone(timedelta(hours=9))).date().isoformat()
        config.update(start_date=day, end_date=day)
    return config
