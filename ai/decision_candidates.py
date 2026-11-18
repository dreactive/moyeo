"""Prepare real service actions for the unchanged judge; never choose or execute them."""
from copy import deepcopy
import hashlib
import json

from ai.auxiliary_grounding import canonical_unsupported, unsupported_clauses, UNSUPPORTED_REASONS
from ai.auxiliary_requests import (ANCHOR_NAMES, CALCULATION_TOOLS, LOOKUP_INTENTS, REQUEST_INTENTS, ROUTE_INTENT, calculation_requested,
                                   cancellable_requests, cancellation_matches, excluded_name, lookup_fields,
                                   lookup_target_evidence, place_observation_in_scope, route_evidence)
from ai.cost_inputs import build_cost_inputs
from ai.grounding import normalized
from ai.planning import (active_place_item, itinerary_arguments, pending_routes, planned_visits,
                         selected_place_items, selected_route_observations)
from ai.questions import question
from ai.tools.context import build_tool_context
from ai.tools.routes import route_matches
from ai.tools.validation import validate_arguments


_ERRORS = (ValueError, KeyError, TypeError, OverflowError)


def _unique(values):
    return list(dict.fromkeys(v for v in values if isinstance(v, str) and v))


def _messages(task):
    return {m["id"]: m for m in task.get("conversation_context", []) + task.get("recent_messages", [])
            if isinstance(m, dict) and m.get("id")}


def _identity(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _candidate(action, reason, arguments=None, tool_name=None, message_ids=(), refs=(), question_value=None):
    value = dict(action=action, reason=reason, tool_name=tool_name, arguments=deepcopy(arguments or {}),
                 source_message_ids=_unique(message_ids), source_refs=_unique(refs))
    identity = [action, tool_name, value["arguments"]]
    if question_value is not None:
        value["question"] = question_value
        identity.append([question_value.get(k) for k in ("field", "target_ref", "owner_id", "target_name")])
    elif action != "tool":
        identity.append(reason)
    value["candidate_id"] = "candidate:" + _identity(identity)
    return value


def _context(task):
    value = deepcopy(task)
    for key in ("items", "constraints", "questions", "observations", "members", "recent_messages"):
        value.setdefault(key, [])
    value.setdefault("config", {})
    for q in value["questions"]:
        if (q.get("status") == "answered" and q.get("field") in ("origin", "destination", "lodging")
                and q.get("owner_id") in (None, q.get("answered_by")) and q.get("answer")):
            value["config"][q["field"]] = deepcopy(q["answer"])
    return build_tool_context(value)


def _provenance(context, item=None, place_refs=()):
    ids = list((item or {}).get("source_message_ids", []))
    refs = [item["id"]] if item and item.get("id") else []
    for ref in place_refs:
        refs.append(ref)
        place = context["places"].get(ref, {})
        if place.get("source_ref"):
            refs.append(place["source_ref"])
        for observation in context["observations"]:
            result = observation.get("result", {})
            places = result.get("places", []) + ([result["place"]] if result.get("place") else [])
            if any(p.get("id") == ref for p in places):
                refs.extend(observation.get("source_refs", []))
    return ids, _unique(refs)


def _resolved_ref(context, item, by_item):
    known = context["places"]
    plan = context.get("current_plan") or {}
    snapshot = next((i for i in plan.get("item_snapshots", []) if i.get("id") == item["id"]), {})
    visit = next((v for d in plan.get("days", []) for v in d.get("visits", []) if v.get("item_id") == item["id"]), {})
    ref = (item.get("place_ref") or snapshot.get("place_ref") or visit.get("place_ref")
           or by_item.get(item["id"], {}).get("place_ref"))
    if ref in known:
        return ref
    for observation in reversed(context["observations"]):
        if observation.get("tool_name") != "search_places":
            continue
        args = observation.get("arguments", {})
        if args.get("query") != item["title"] or args.get("region") != context["config"].get("region"):
            continue
        places = observation.get("result", {}).get("places", [])
        exact = [p for p in places if p.get("name") == item["title"]]
        matches = exact or places
        return matches[0]["id"] if len(matches) == 1 else None
    return None


def _ordered_items(context):
    def position(indexed):
        original, item = indexed
        sources = set(item.get("source_message_ids", []))
        for order, message in enumerate(context["recent_messages"]):
            text = message.get("text", "")
            title_at = text.find(item.get("title", "")) if item.get("title") else -1
            if message.get("id") in sources or title_at >= 0:
                return order, title_at if title_at >= 0 else len(text), original
        return len(context["recent_messages"]), 0, original
    return [item for _, item in sorted(enumerate(selected_place_items(context)), key=position)]


def _tool_candidates(context, calculation=None):
    candidates = []
    try:
        visits = planned_visits(context)
    except _ERRORS:
        visits = []
    active = _ordered_items(context)
    by_item = {v["item_id"]: v for v in visits}
    inactive = {i["id"] for i in context["items"] if not active_place_item(i)}
    inactive_refs = {v["place_ref"] for v in visits if v.get("item_id") in inactive}

    def add(name, arguments, reason, ids=(), refs=()):
        if name in ("get_car_route", "build_itinerary", "calculate_costs") and context["config"].get("transport", "car") != "car":
            return
        try:
            validate_arguments(name, arguments, context)
        except _ERRORS:
            return
        if name == "get_place_details":
            already_observed = arguments["place_ref"] in context.get("detail_attempts", {})
        else:
            already_observed = any(o.get("tool_name") == name and o.get("arguments") == arguments
                                   and (name != "get_car_route" or route_matches(o, context, arguments))
                                   for o in context["observations"])
        if already_observed:
            return
        previous = next((c for c in candidates if c["tool_name"] == name and c["arguments"] == arguments), None)
        if previous:
            previous["source_message_ids"] = _unique(previous["source_message_ids"] + list(ids))
            previous["source_refs"] = _unique(previous["source_refs"] + list(refs))
        else:
            candidates.append(_candidate("tool", reason, arguments, name, ids, refs))

    for item in active:
        ref = _resolved_ref(context, item, by_item)
        if ref:
            ids, refs = _provenance(context, item, [ref])
            if ref not in context["details"]:
                add("get_place_details", dict(place_ref=ref), "방문 장소의 실제 가격과 운영시간을 조회합니다.", ids, refs)
        elif isinstance(item.get("title"), str) and item["title"].strip():
            region = context["config"].get("region")
            if isinstance(region, str) and region.strip():
                ids, refs = _provenance(context, item)
                add("search_places", dict(query=item["title"], region=region, category=None),
                    "요청한 장소를 방의 지역에서 검색합니다.", ids, refs)

    if calculation or active or context.get("current_plan") is not None or context["config"].get("fixed_costs"):
        try:
            routes = pending_routes(context)
        except _ERRORS:
            routes = []
        for arguments in routes:
            endpoints = [arguments["from_ref"], arguments["to_ref"]]
            if any(ref in inactive_refs for ref in endpoints):
                continue
            related = [i for i in active if by_item.get(i["id"], {}).get("place_ref") in endpoints]
            ids = [mid for i in related for mid in i.get("source_message_ids", [])]
            _, refs = _provenance(context, place_refs=endpoints)
            try:
                prior = [o for o in selected_route_observations(context)
                         if (o.get("arguments", {}).get("departure_at") or "")[:10] == arguments["departure_at"][:10]]
            except _ERRORS:
                prior = []
            refs += [o["result"]["evidence_id"] for o in prior if o.get("result", {}).get("evidence_id")]
            refs += [ref for o in prior for ref in o.get("source_refs", [])]
            add("get_car_route", arguments, "확인된 거점과 방문 장소 사이의 해당 출발시각 자동차 경로를 조회합니다.", ids, refs)
        if not any(v.get("item_id") in inactive for v in visits):
            for name, builder in (("build_itinerary", itinerary_arguments), ("calculate_costs", lambda c: build_cost_inputs(c)[0])):
                try:
                    arguments = builder(context)
                except _ERRORS:
                    continue
                ids = [mid for i in active for mid in i.get("source_message_ids", [])]
                refs = [ref for o in context["observations"] for ref in o.get("source_refs", [])]
                refs += [o["result"]["evidence_id"] for o in context["observations"] if o.get("result", {}).get("evidence_id")]
                refs += [i["id"] for i in active] + [v["place_ref"] for v in visits]
                refs += [c["id"] for c in context["constraints"] if c.get("id")]
                add(name, arguments, "확인된 사용자 입력과 실제 관측으로 계산합니다.", ids, refs)
    return candidates


def _saved_request(context, request):
    fields = ("request_id", "intent", "owner_id", "source_message_id", "evidence", "target_names",
              "excluded_names", "target_refs", "excluded_refs", "context_evidence", "requested_fields",
              "operation", "cancelled_request_ids", "prior_request_ids", "answer", "unsupported_code", "unsupported_reason",
              "route_timing", "departure_at")
    return next((saved for saved in context.get("pending_requests", []) or [] if isinstance(saved, dict)
                 and all(saved.get(field) == request.get(field) for field in fields)), None)


def _request_evidence(context, request):
    if (not isinstance(request, dict) or request.get("intent") not in REQUEST_INTENTS
            or not request.get("request_id") or request.get("operation", "request") not in ("request", "cancel")):
        return None
    owner, source = request.get("owner_id"), request.get("source_message_id")
    if owner not in {m.get("user_id") for m in context["members"]}:
        return None
    evidence = request.get("evidence", {})
    quote = evidence.get("quote")
    if evidence.get("message_id") != source or not isinstance(quote, str) or not quote:
        return None
    saved = _saved_request(context, request)
    current = {m["id"]: m for m in context["recent_messages"]}
    known = _messages(context)
    message = known.get(source)
    if saved is None and source not in current:
        return None
    expected_id = "request:" + (source or "") + ":" + request["intent"]
    if saved is None and request["request_id"] != expected_id and not request["request_id"].startswith(expected_id + ":"):
        return None
    if message and (message.get("author_id") != owner or quote not in message.get("text", "")
                    or message.get("room_id") not in (None, context.get("room_id"))):
        return None
    operation = request.get("operation", "request")
    if request["intent"] == "service_request" and operation == "request":
        code = request.get("unsupported_code")
        if code not in UNSUPPORTED_REASONS or request.get("unsupported_reason") != UNSUPPORTED_REASONS[code]:
            return None
        if message and (quote, code) not in unsupported_clauses(message["text"]):
            return None
    elif request["intent"] in CALCULATION_TOOLS and operation == "request":
        if not calculation_requested(request["intent"], message["text"] if message else quote, quote):
            return None
    elif request["intent"] == ROUTE_INTENT and operation == "request":
        route = route_evidence(request, message["text"] if message else quote)
        owner_answered = saved and isinstance(saved.get("answer"), dict)
        if not owner_answered and (route is None or route[1:] != (request.get("route_timing"), request.get("departure_at"))
                                  or request.get("target_names") and not route[0]):
            return None
    elif lookup_fields(request, message["text"] if message else quote) is None and saved is None:
        return None
    ids, quotes = [source], [quote]
    for item in request.get("context_evidence", []):
        mid, text, author = item.get("message_id"), item.get("quote"), item.get("author_id")
        original = known.get(mid)
        if author != owner or mid == source or not isinstance(text, str) or not text:
            return None
        if original is None and saved is None:
            return None
        if original and (original.get("author_id") != author or text not in original.get("text", "")
                         or original.get("room_id") not in (None, context.get("room_id"))):
            return None
        if mid in current and source in current and list(current).index(mid) >= list(current).index(source):
            return None
        ids.append(mid)
        quotes.append(text)
    return _unique(ids), quotes, saved


def _request_places(context, explicit_refs=()):
    places, sources, observations = {}, {}, []
    room = context.get("room_id")
    for observation in context["observations"]:
        if not place_observation_in_scope(context, observation, explicit_refs):
            continue
        result = observation.get("result", {})
        observations.append(observation)
        proof = _unique([observation.get("id"), observation.get("observation_id")] + observation.get("source_refs", []))
        for place in result.get("places", []) + ([result["place"]] if result.get("place") else []):
            if place.get("room_id") not in (None, room) or not place.get("id"):
                continue
            ref = place["id"]
            places[ref] = place
            sources[ref] = _unique(sources.get(ref, []) + proof + [place.get("source_ref")])
    return places, sources, observations


def _record_candidate(candidates, candidate, request, name=None, ref=None, result_refs=()):
    request_id = request["request_id"]
    target = dict(request_id=request_id, target_name=name, target_ref=ref)
    previous = next((c for c in candidates if c["candidate_id"] == candidate["candidate_id"]), None)
    if previous is None:
        previous = dict(candidate, request_ids=[], request_targets=[], result_refs=[])
        candidates.append(previous)
    for key, values in (("source_message_ids", candidate["source_message_ids"]), ("source_refs", candidate["source_refs"]),
                        ("request_ids", [request_id]), ("result_refs", list(result_refs))):
        previous[key] = _unique(previous[key] + values)
    if target not in previous["request_targets"]:
        previous["request_targets"].append(target)
    return previous


def _location_text(place):
    name = place["name"]
    if place.get("address"):
        return name + " · " + place["address"]
    if place.get("latitude") is not None and place.get("longitude") is not None:
        return f'{name} · {place["latitude"]}, {place["longitude"]}'
    return name + " · 주소 미확인"


def _details_text(place, details, fields):
    parts = [_location_text(place) if {"details", "location"} & set(fields) else place["name"]]
    if {"details", "price"} & set(fields):
        prices = [f'{row["name"]} {row["price_krw"]:,}원' for row in details.get("menus", [])
                  if row.get("name") and type(row.get("price_krw")) is int]
        parts.append(", ".join(prices[:5]) if prices else "가격 미확인")
    if {"details", "opening_hours"} & set(fields):
        hours = details.get("opening_hours") or {}
        rows = [f'{i["day"]} {i["start"]}–{i["end"]}' for i in hours.get("intervals") or []
                if all(i.get(k) for k in ("day", "start", "end"))]
        try:
            closure = json.loads(hours.get("holiday_text") or "{}")
        except ValueError:
            closure = None
        if isinstance(closure, dict):
            rows.extend(day + " 휴무" for day in closure.get("closed_dates", []) if isinstance(day, str))
        if not rows or "opening_hours" in details.get("missing_fields", []):
            rows = rows[:4] + ["일부 영업시간 미확인" if rows else "영업시간 미확인"]
        parts.append(", ".join(rows[:5]))
    return " · ".join(parts)


def _search_observation(observations, name, region):
    return next((o for o in reversed(observations) if o["tool_name"] == "search_places"
                 and normalized(o.get("arguments", {}).get("query") or "") == normalized(name)
                 and o.get("arguments", {}).get("region") == region and "places" in o.get("result", {})), None)


def _request_question(context, candidates, request, ids, name=None, choices=(), field="target_places"):
    ref, owner = request["request_id"], request["owner_id"]
    if field == "region":
        text, ref = "어느 지역에서 장소를 찾아볼까요?", "config:region"
    elif field in ("origin", "destination", "lodging"):
        text, ref = f'{name}의 위치를 알려주세요.', "anchor:" + field
    elif field == "route_departure":
        text = "자동차로 출발할 날짜와 시간을 알려주세요."
    elif request.get("operation") == "cancel":
        text = "어떤 조회 요청을 취소할까요?"
        owned = cancellable_requests(context, owner, request["source_message_id"])
        scopes = [", ".join(r.get("target_names", [])) for r in owned if r.get("target_names")]
        if scopes:
            text += " " + " / ".join(scopes)
    elif choices:
        text = f'{name}의 어느 지점을 조회할까요? ' + " / ".join(_location_text(place) for place in choices)
    elif request["intent"] == ROUTE_INTENT and name:
        text = f'{name}의 위치를 찾지 못했습니다. 이 지점의 다른 이름이나 주소를 알려주세요.'
    elif request["intent"] == ROUTE_INTENT:
        text = "자동차 경로의 출발지와 도착지는 어디인가요?"
    else:
        labels = {"location":"위치", "price":"가격", "opening_hours":"영업시간", "details":"상세 정보"}
        fields = "·".join(labels[f] for f in request.get("requested_fields", []) if f in labels)
        text = f"어느 장소의 {fields} 정보를 확인할까요?" if fields else "어느 장소를 조회할까요?"
    if any(q.get("status") == "open" and (q.get("field"), q.get("target_ref"), q.get("owner_id"), q.get("target_name"))
           == (field, ref, owner, name) for q in context["questions"]):
        return
    q = question(field, ref, text, owner)
    q["id"] = "question:" + field + ":" + _identity([ref, owner, name])
    q["source_message_ids"] = ids
    if name is not None:
        q["target_name"] = name
    if choices:
        q["place_choices"] = [dict(place_ref=p["id"], name=p["name"], address=p.get("address") or "") for p in choices]
    candidate = _candidate("ask", text, message_ids=ids, refs=[p["id"] for p in choices], question_value=q)
    _record_candidate(candidates, candidate, request, name)


def _route_candidate(context, candidates, request, route_refs, sources, ids):
    names = request["target_names"]
    if len(names) != 2 or any(name not in route_refs for name in names):
        return
    start, end = (route_refs[name] for name in names)
    if start == end:
        return
    if request["route_timing"] == "needs_input":
        _request_question(context, candidates["ask"], request, ids, field="route_departure")
        return
    arguments = dict(from_ref=start, to_ref=end, departure_at=request.get("departure_at"))
    try:
        validate_arguments("get_car_route", arguments, context)
    except _ERRORS:
        if request["route_timing"] == "scheduled":
            _request_question(context, candidates["ask"], request, ids, field="route_departure")
        return
    proof = _unique([start, end] + sources.get(start, []) + sources.get(end, []))
    room = context.get("room_id")
    observation = next((o for o in reversed(context["observations"])
                        if o.get("room_id") in (None, room) and o.get("result", {}).get("room_id") in (None, room)
                        and route_matches(o, context, arguments)), None)
    if observation:
        route = observation["result"]
        seconds = route["duration_seconds"]
        response = [f'{names[0]} → {names[1]}', f'{seconds // 60}분 {seconds % 60}초']
        if route.get("distance_m") is not None:
            response.append(f'{route["distance_m"]:,}m')
        toll = route.get("toll_krw")
        response.append(f'통행료 {toll:,}원' if toll is not None else "통행료 미확인")
        result_refs = _unique([observation.get("id"), route.get("evidence_id")] + observation.get("source_refs", []))
        candidate = _candidate("direct", " · ".join(response), message_ids=ids, refs=proof + result_refs)
        _record_candidate(candidates["direct"], candidate, request, result_refs=result_refs)
    else:
        purpose = "현재" if request["route_timing"] == "current" else arguments["departure_at"]
        reason = f'{purpose} 출발 기준 {names[0]}에서 {names[1]}까지 자동차 경로를 조회합니다.'
        candidate = _candidate("tool", reason, arguments, "get_car_route", ids, proof)
        _record_candidate(candidates["tool"], candidate, request)


def _request_candidates(context, requests):
    """Prepare each grounded target against observed identities and request-local progress."""
    candidates = {action: [] for action in ("tool", "ask", "direct", "unsupported")}
    if not isinstance(requests, list):
        return candidates
    known = _messages(context)
    current_order = {m["id"]: index for index, m in enumerate(context["recent_messages"])}
    ordered = sorted(enumerate(requests), key=lambda pair: (current_order.get(
        pair[1].get("source_message_id") if isinstance(pair[1], dict) else None, len(current_order)), pair[0]))
    for _, request in ordered:
        provenance = _request_evidence(context, request)
        if (provenance is None or request.get("status") not in ("resolved", "pending", "needs_input")
                or request.get("request_id") in context.get("_blocked_request_ids", ())):
            continue
        ids, quotes, saved = provenance
        state = saved or request
        if state.get("status") in ("completed", "cancelled", "superseded", "unsupported", "failed"):
            continue
        refs = request.get("target_refs", [])
        names = request.get("target_names", [])
        if not isinstance(refs, list) or not isinstance(names, list) or any(not isinstance(n, str) or not n for n in names):
            continue
        if request.get("operation") == "cancel":
            matching = cancellation_matches(context, request["owner_id"], names, request["source_message_id"])
            if matching and (matching == request.get("cancelled_request_ids") or saved and saved.get("answer")):
                response = "요청한 조회를 취소했습니다."
                candidate = _candidate("direct", response, message_ids=ids)
                direct = _record_candidate(candidates["direct"], candidate, request)
                direct["cancelled_request_ids"] = _unique(direct.get("cancelled_request_ids", []) + matching)
            elif not cancellable_requests(context, request["owner_id"], request["source_message_id"]):
                response = "취소할 수 있는 내 진행 중 조회가 없습니다."
                _record_candidate(candidates["direct"], _candidate("direct", response, message_ids=ids), request)
            else:
                _request_question(context, candidates["ask"], request, ids)
            continue
        if request["intent"] == "service_request":
            candidate = _candidate("unsupported", request["unsupported_reason"], message_ids=ids)
            _record_candidate(candidates["unsupported"], candidate, request)
            continue
        if request["intent"] in CALCULATION_TOOLS:
            tool_name = CALCULATION_TOOLS[request["intent"]]
            prepared = _tool_candidates(context, calculation=tool_name)
            ready = [c for c in prepared if c['tool_name'] == tool_name]
            prerequisites = {'search_places', 'get_car_route'} if tool_name=='build_itinerary' else {'search_places', 'get_place_details'}
            offered = ready or [c for c in prepared if c['tool_name'] in prerequisites]
            for candidate in offered:
                candidate['source_message_ids'] = _unique(ids + candidate['source_message_ids'])
                _record_candidate(candidates['tool'], candidate, request)
            if not offered:
                reason = ('배치할 방문 장소와 날짜, 출발 거점 및 해당 구간의 경로를 확인해야 일정을 계산할 수 있습니다.'
                          if tool_name=='build_itinerary' else '비용을 분담할 참가자와 예산, 비용 항목을 확인해주세요.')
                candidate = _candidate('direct', reason, message_ids=ids)
                _record_candidate(candidates['direct'], candidate, request)
            continue
        if not names:
            if request.get("status") == "needs_input":
                _request_question(context, candidates["ask"], request, ids)
            continue
        legacy = request["intent"] == "place_details" and not request.get("requested_fields")
        places, sources, observations = _request_places(context, refs if saved else ())
        execution_context = build_tool_context(dict(context, observations=observations))
        if legacy and (len(names) != len(refs) or any(ref not in places for ref in refs)):
            continue
        fields = set(request.get("requested_fields") or ("details" if legacy else "location",))
        is_route = request["intent"] == ROUTE_INTENT
        route_refs = {}
        excluded = set(request.get("excluded_refs", []))
        excluded_names = set(map(normalized, request.get("excluded_names", [])))
        answers = [q["answer"] for q in context["questions"] if q.get("field") == "target_places"
                   and q.get("target_ref") == request["request_id"] and q.get("status") == "answered"
                   and q.get("answered_by") == request["owner_id"] and isinstance(q.get("answer"), dict)]
        if saved and saved.get("answer"):
            answers.append(saved["answer"])
        completed_names = set(map(normalized, state.get("completed_target_names", [])))
        failed_names = {normalized(f["target_name"]) for f in state.get("failed_targets", []) if f.get("target_name")}
        prior = {mid: message for mid, message in known.items() if mid in ids[1:]
                 or mid in current_order and current_order[mid] < current_order.get(ids[0], 0)}
        current = known.get(ids[0])

        def target_position(name):
            for order, quote in enumerate(quotes):
                at = normalized(quote).find(normalized(name))
                if at >= 0:
                    return order, at
            return len(quotes), 0

        for name in sorted(names, key=target_position):
            target = normalized(name)
            if target in excluded_names or target in completed_names or target in failed_names:
                continue
            answered = next((answer for answer in reversed(answers) if name in answer.get("target_names", [])), {})
            answered_name = bool(answered)
            if not answered_name and (not any(target in normalized(text) for text in quotes) or
                    not is_route and current and all(mid in prior for mid in ids[1:])
                    and not lookup_target_evidence(name, current, request["evidence"], request.get("context_evidence", []), prior, fields)):
                continue
            if current is None and any(excluded_name(name, text) for text in quotes) and not answered_name:
                continue
            anchor = ANCHOR_NAMES.get(target) if is_route else None
            if anchor:
                if anchor in context["places"]:
                    route_refs[name] = anchor
                else:
                    _request_question(context, candidates["ask"], request, ids, name, field=anchor.split(":")[1])
                continue
            region = context["config"].get("region")
            search = _search_observation(observations, name, region)
            options = [place for ref, place in places.items() if ref not in excluded
                       and normalized(place.get("name") or "") == target and (not legacy or ref in refs)]
            if not options and search and not legacy:
                options = [places[p["id"]] for p in search["result"]["places"] if p.get("id") in places and p["id"] not in excluded]
            chosen_ref = answered.get("place_ref") if answered_name else None
            if chosen_ref and any(p["id"] == chosen_ref for p in options):
                options = [places[chosen_ref]]
            if options and fields == {"location"} and not is_route:
                direct_text = " / ".join(_location_text(place) for place in options)
                for place in options:
                    ref = place["id"]
                    if ref not in state.get("completed_refs", []):
                        proof = _unique([ref] + sources.get(ref, []))
                        candidate = _candidate("direct", direct_text, message_ids=ids, refs=proof)
                        _record_candidate(candidates["direct"], candidate, request, name, ref, proof)
                continue
            if options and (len(options) > 1 or not chosen_ref and normalized(options[0].get("name") or "") != target):
                _request_question(context, candidates["ask"], request, ids, name, options)
                continue
            if not options and search and not legacy:
                if is_route:
                    _request_question(context, candidates["ask"], request, ids, name)
                    continue
                proof = _unique([search.get("id"), search.get("observation_id")] + search.get("source_refs", []))
                candidate = _candidate("direct", f'{name}의 검색 결과가 없습니다.', message_ids=ids, refs=proof)
                _record_candidate(candidates["direct"], candidate, request, name, result_refs=proof)
                continue
            ref = options[0]["id"] if options else None
            if is_route and ref:
                route_refs[name] = ref
                continue
            if ref in state.get("completed_refs", []) or legacy and saved and ref not in saved.get("pending_refs", refs):
                continue
            proof = _unique([ref] + sources.get(ref, []))
            if ref:
                details = execution_context["details"].get(ref)
                if details:
                    if (not legacy or saved) and details.get("match_status", "matched") == "matched":
                        response = _details_text(places[ref], details, fields)
                        candidate = _candidate("direct", response, message_ids=ids, refs=proof)
                        _record_candidate(candidates["direct"], candidate, request, name, ref, proof)
                    continue
                tool, arguments = "get_place_details", dict(place_ref=ref)
                reason = f'{name}의 요청한 상세 정보를 조회합니다.'
            elif not legacy and isinstance(region, str) and region.strip():
                tool, arguments = "search_places", dict(query=name, region=region, category=None)
                reason = f'{region}에서 {name}의 위치를 검색합니다.'
                proof = ["config:region"]
            else:
                if not legacy:
                    _request_question(context, candidates["ask"], request, ids, field="region")
                continue
            try:
                validate_arguments(tool, arguments, execution_context)
            except _ERRORS:
                continue
            candidate = _candidate("tool", reason, arguments, tool, ids, proof)
            _record_candidate(candidates["tool"], candidate, request, name, ref)
        if is_route:
            route_context = dict(context, places={ref: context["places"][ref] for ref in route_refs.values()
                                                 if ref in context["places"]})
            _route_candidate(route_context, candidates, request, route_refs, sources, ids)
    requests_by_id = {r["request_id"]: r for r in requests if isinstance(r, dict) and r.get("request_id")}

    def candidate_position(candidate):
        positions = []
        for target in candidate["request_targets"]:
            request = requests_by_id[target["request_id"]]
            source = request["source_message_id"]
            text = known.get(source, {}).get("text", "")
            offset = normalized(text).find(normalized(target["target_name"] or ""))
            positions.append((current_order.get(source, len(current_order)), offset if offset >= 0 else len(text)))
        return min(positions)

    for values in candidates.values():
        values.sort(key=candidate_position)
    return candidates


def _analysis_sources(task, analysis):
    known = _messages(task)
    supplied = analysis.get("source_message_ids")
    ids = supplied if supplied is not None else [m["id"] for m in task.get("recent_messages", []) if m.get("id")]
    if not isinstance(ids, list) or any(mid not in known for mid in ids):
        return None
    return _unique(ids)


def _known_refs(context):
    refs = set(context["places"])
    refs.update("config." + key for key in context["config"])
    refs.update("config:" + key for key in context["config"])
    refs.update(i["id"] for i in context["items"] if i.get("id"))
    refs.update(c["id"] for c in context["constraints"] if c.get("id"))
    refs.update(p["source_ref"] for p in context["places"].values() if p.get("source_ref"))
    for observation in context["observations"]:
        refs.update(observation.get("source_refs", []))
        result = observation.get("result", {})
        if result.get("evidence_id"):
            refs.add(result["evidence_id"])
        refs.update(e["id"] for e in result.get("evidence", []) if e.get("id"))
    return refs


def _grounded_direct(context, text):
    values = [c.get("value") for c in context["constraints"] if c.get("status") == "confirmed"]
    values.extend(v for v in context["config"].values() if isinstance(v, (str, int, float, bool)))
    values.extend(i.get("title") for i in context["items"])
    return any(text == str(value) for value in values if value is not None)


def _question_target_valid(context, field, ref, owner):
    members = {m.get("user_id") for m in context["members"]}
    if owner is not None and owner not in members:
        return False
    if field in ("origin", "destination", "lodging"):
        return ref == "anchor:" + field
    if field in ("region", "start_date", "end_date", "travel_date", "transport"):
        return ref == "config:" + field and not context["config"].get(field)
    if field in ("menu_selection", "visit_duration"):
        return any(i.get("id") == ref and active_place_item(i) for i in context["items"])
    if field == "constraint_value":
        return any(c.get("id") == ref and c.get("owner_id") == owner for c in context["constraints"])
    if field == "support_target":
        return owner is not None and (ref is None or any(i.get("id") == ref for i in context["items"]))
    return False


def _question_key(value):
    return tuple(value.get(k) for k in ("field", "target_ref", "owner_id"))


def _missing_questions(context, analysis):
    opened = {_question_key(q) for q in context["questions"] if q.get("status") == "open"}
    seen, result = set(opened), []
    for missing in analysis.get("missing_fields", []) or []:
        if not isinstance(missing, dict):
            continue
        field, ref, owner = _question_key(missing)
        text = missing.get("text")
        if not field or (not ref and field != "support_target") or not isinstance(text, str) or not text.strip():
            continue
        if not _question_target_valid(context, field, ref, owner):
            continue
        if missing.get("source") in ("history", "context", "tool", "observation", "tool_observation"):
            continue
        if field in ("origin", "destination", "lodging") and context["config"].get(field):
            continue
        key = _question_key(missing)
        if key in seen:
            continue
        ids = _analysis_sources(context, missing)
        if ids is None:
            continue
        if field == "support_target":
            current = {m["id"]: m for m in context["recent_messages"]}
            stance = missing.get("stance")
            if (stance not in ("support", "oppose", "withdraw") or len(ids) != 1
                    or ids[0] not in current or current[ids[0]].get("author_id") != owner):
                continue
        seen.add(key)
        q = question(field, ref, text, owner, [ref] if any(i.get("id") == ref for i in context["items"]) else [])
        q["id"] = ("question:support_target:" + missing["stance"] + ":" + ids[0] if field == "support_target"
                   else "question:" + field + ":" + _identity(key))
        q["source_message_ids"] = ids
        result.append(_candidate("ask", text, message_ids=ids, refs=[ref], question_value=q))
        if len(result) == 2:
            break
    return result


def build_decision_candidates(task: dict, analysis: dict | None = None) -> dict:
    """Return only prepared real choices; preserve all task/pending state in the caller."""
    analysis = analysis if isinstance(analysis, dict) else {}
    requests = analysis.get("requests")
    if analysis.get("lookup_scope_rejected") and not requests:
        return dict(branch="invalid", candidates=[])
    if analysis.get("noop") is True and not requests:
        return dict(branch="noop", candidates=[])
    context = _context(task)
    scoped = _request_candidates(context, requests)
    calls = scoped["tool"] if requests else _tool_candidates(context)
    ids = _analysis_sources(task, analysis)
    source_refs = analysis.get("source_refs", [])
    if not isinstance(source_refs, list) or not set(source_refs) <= _known_refs(context):
        ids = None
    unsupported = scoped["unsupported"][:1]
    service_limit = canonical_unsupported(context)
    if not requests and service_limit["unsupported"]:
        unsupported = [_candidate("unsupported", service_limit["unsupported_reason"],
            message_ids=service_limit["source_message_ids"], refs=service_limit["source_refs"])]
    if calls:
        prepared = dict(branch="valid", candidates=calls[:3] + unsupported)
        if len(calls) > 3:
            prepared["deferred_candidates"] = calls[3:]
        return prepared
    questions = scoped["ask"]
    has_lookup = any(isinstance(r, dict) and r.get("intent") in (*LOOKUP_INTENTS, ROUTE_INTENT) for r in requests or [])
    if not requests or has_lookup:
        extra = _missing_questions(context, analysis)
        if requests:
            extra = [c for c in extra if c["question"]["field"] == "region"]
        questions = (questions + extra)[:2]
    candidates = questions + unsupported + scoped["direct"][:max(1, 4 - len(questions) - len(unsupported))]
    text = analysis.get("direct_text")
    if not requests and isinstance(text, str) and text.strip() and ids and _grounded_direct(context, text):
        candidates.append(_candidate("direct", text, message_ids=ids, refs=analysis.get("source_refs", [])))
    return dict(branch="invalid", candidates=candidates)


def _small(value):
    if isinstance(value, dict):
        return {k: _small(v) for k, v in value.items() if k not in ("polyline", "conversation_context")}
    if isinstance(value, list):
        return [_small(v) for v in value]
    return deepcopy(value)


def _fields(value, fields):
    return {k: _small(value[k]) for k in fields if k in value}


def compact_decision_context(task: dict, analysis: dict | None, candidates: list[dict]) -> dict:
    """Keep deciding facts and original evidence, excluding raw provider response bodies."""
    analysis = analysis if isinstance(analysis, dict) else {}
    context = _context(task)
    ids = _unique([mid for c in candidates for mid in c.get("source_message_ids", [])])
    refs = _unique([ref for c in candidates for ref in c.get("source_refs", [])])
    known_messages = _messages(task)
    requests = [r for r in analysis.get("requests", []) or [] if isinstance(r, dict) and _request_evidence(context, r) is not None]
    ids = _unique(ids + [mid for request in requests for mid in _request_evidence(context, request)[0]])
    current = task.get("recent_messages", [])
    current_ids = {m.get("id") for m in current}
    message_fields = ("id", "author_id", "text")
    config_fields = ("region", "start_date", "end_date", "transport", "day_start_time", "day_end_time",
                     "origin", "destination", "lodging", "per_person_budget_krw", "fixed_costs")
    facts = dict(config=_fields(context["config"], config_fields),
                 items=[_fields(i, ("id", "item_version", "kind", "title", "state", "supporter_ids", "opponent_ids",
                                    "owner_id", "source_message_ids", "evidence", "included_in_plan")) for i in context["items"]],
                 constraints=_small(context["constraints"]),
                 answers=[_fields(q, ("id", "field", "target_ref", "owner_id", "text", "status", "answer", "answered_by", "source_message_ids"))
                          for q in context["questions"] if q.get("status") == "answered"])

    if any(c.get("tool_name") in ("get_car_route", "build_itinerary", "calculate_costs") for c in candidates):
        try:
            facts["visits"] = _small(planned_visits(context))
        except _ERRORS:
            facts["visits"] = []
    referenced = set(refs)
    referenced.update(ref for request in requests for ref in request.get("target_refs", []) + request.get("excluded_refs", []))
    for candidate in candidates:
        args = candidate.get("arguments", {})
        referenced.update(args[k] for k in ("place_ref", "from_ref", "to_ref") if k in args)
        referenced.update(v["place_ref"] for v in args.get("visits", []) if v.get("place_ref"))
    places = context["places"]
    if analysis.get("requests"):
        places, place_sources, _ = _request_places(context)
        places.update({ref: place for ref, place in context["places"].items() if ref.startswith("anchor:")})
        facts["place_source_refs"] = {ref: proof for ref, proof in place_sources.items() if ref in referenced}
    facts["places"] = {ref: _fields(p, ("id", "name", "label", "address", "latitude", "longitude", "source_ref"))
                       for ref, p in places.items() if ref in referenced}
    facts["details"] = {ref: _fields(d, ("menus", "opening_hours", "evidence"))
                        for ref, d in context["details"].items() if ref in referenced}
    facts["route_facts"] = [_fields(o["result"], ("from_ref", "to_ref", "duration_seconds", "distance_m", "toll_krw", "evidence_id"))
                            | {"arguments": _small(o.get("arguments", {}))}
                            for o in context["observations"] if o.get("tool_name") == "get_car_route"
                            and (o.get("result", {}).get("evidence_id") in referenced
                                 or any(c.get("tool_name") in ("build_itinerary", "calculate_costs") for c in candidates))]
    return dict(goal=task.get("goal"), current_messages=[_fields(m, message_fields) for m in current], facts=facts,
                source_messages=[_fields(known_messages[mid], message_fields) for mid in ids if mid in known_messages and mid not in current_ids],
                source_refs=refs, missing_fields=_small(analysis.get("missing_fields", [])),
                open_questions=[_fields(q, ("id", "field", "target_ref", "owner_id", "text", "status"))
                                for q in context["questions"] if q.get("status") == "open"],
                summary=analysis.get("summary", ""),
                **({"requests": [_fields(request, ("request_id", "intent", "owner_id", "source_message_id", "evidence",
                    "target_names", "excluded_names", "target_refs", "excluded_refs", "context_evidence", "status",
                    "requested_fields", "operation", "unresolved_target_names", "cancelled_request_ids",
                    "unsupported_reason", "route_timing", "departure_at"))
                                  for request in requests]} if analysis.get("requests") else {}))
