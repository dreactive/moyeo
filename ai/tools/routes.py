from copy import deepcopy
from datetime import datetime, timedelta, timezone
from math import isfinite

from ai.providers.kakao import route_evidence_id


CURRENT_ROUTE_MAX_AGE = timedelta(minutes=5)
FUTURE_ROUTE_MAX_AGE = timedelta(days=1)


def aware_datetime(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
    return parsed if parsed.utcoffset() is not None else None


def valid_route_request(context, arguments, now=None):
    for key in ("from_ref", "to_ref"):
        place = context["places"].get(arguments[key], {})
        if any(type(place.get(k)) not in (int, float) or not isfinite(place[k]) or abs(place[k]) > limit
               for k, limit in (("latitude", 90), ("longitude", 180))):
            return False
    departure = arguments["departure_at"]
    if departure is None:
        return True
    parsed = aware_datetime(departure)
    if not parsed:
        return False
    if context.get("_provider_mode") == "live":
        return parsed.replace(second=0, microsecond=0) > (now or datetime.now(timezone.utc))
    return True


def route_matches(observation, context, arguments):
    if observation["tool_name"] != "get_car_route" or observation["arguments"] != arguments:
        return False
    leg = observation["result"]
    if (not all(leg.get(key) == arguments[key] for key in ("from_ref", "to_ref"))
            or type(leg.get("duration_seconds")) is not int or leg["duration_seconds"] < 0):
        return False
    evidence = leg.get("evidence_id", "")
    live = evidence.startswith("kakao:route:")
    mode = context.get("_provider_mode")
    now = datetime.now(timezone.utc)
    if not valid_route_request(context, arguments, now):
        return False
    if not live:
        return mode != "live"
    if (leg.get("departure_at", arguments["departure_at"]) != arguments["departure_at"]
            or evidence != route_evidence_id(context["places"], arguments)):
        return False
    # Historic fixtures may simulate a Kakao evidence ID without fetching it.
    time = leg.get("retrieved_at") or observation.get("observed_at")
    if time is None and mode != "live" and arguments["departure_at"]:
        return True
    retrieved = aware_datetime(time)
    departure = aware_datetime(arguments["departure_at"])
    max_age = FUTURE_ROUTE_MAX_AGE if departure else CURRENT_ROUTE_MAX_AGE
    return bool(retrieved and timedelta() <= now - retrieved <= max_age and (not departure or now < departure))


def observed_route(context, arguments):
    for key in ("from_ref", "to_ref"):
        if arguments[key] not in context["places"]:
            raise ValueError("Route endpoint not observed")
    for observation in reversed(context.get("observations", [])):
        if route_matches(observation, context, arguments):
            leg = deepcopy(observation["result"])
            if leg.get("evidence_id", "").startswith("kakao:route:"):
                leg.setdefault("retrieved_at", observation.get("observed_at"))
            return leg
    raise ValueError("Route leg missing; never substitute zero seconds")
