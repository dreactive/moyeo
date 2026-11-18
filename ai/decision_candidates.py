"""Prepare real service actions for the unchanged judge; never choose or execute them."""
from copy import deepcopy
import hashlib
import json

from ai.auxiliary_grounding import canonical_unsupported
from ai.cost_inputs import build_cost_inputs
from ai.grounding import normalized
from ai.planning import itinerary_arguments, pending_routes, planned_visits, selected_route_observations
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
        identity.append([question_value.get(k) for k in ("field", "target_ref", "owner_id")])
    elif action != "tool":
        identity.append(reason)
    value["candidate_id"] = "candidate:" + _identity(identity)
    return value


def _eligible(item):
    if item.get("kind") != "place" or item.get("active") is False:
        return False
    if item.get("state") in ("inactive", "opposed", "rejected", "excluded", "removed", "archived", "deleted", "dropped"):
        return False
    return not (item.get("opponent_ids") and not item.get("supporter_ids"))


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
    return [item for _, item in sorted(enumerate(context["items"]), key=position) if _eligible(item)]


def _tool_candidates(context):
    candidates = []
    try:
        visits = planned_visits(context)
    except _ERRORS:
        visits = []
    active = _ordered_items(context)
    by_item = {v["item_id"]: v for v in visits}
    inactive = {i["id"] for i in context["items"] if not _eligible(i)}
    inactive_refs = {v["place_ref"] for v in visits if v.get("item_id") in inactive}

    def add(name, arguments, reason, ids=(), refs=()):
        if name in ("get_car_route", "build_itinerary", "calculate_costs") and context["config"].get("transport", "car") != "car":
            return
        try:
            validate_arguments(name, arguments, context)
        except _ERRORS:
            return
        if any(o.get("tool_name") == name and o.get("arguments") == arguments
               and (name != "get_car_route" or route_matches(o, context, arguments))
               for o in context["observations"]):
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

    if active or context.get("current_plan") is not None:
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
              "excluded_names", "target_refs", "excluded_refs", "context_evidence")
    return next((saved for saved in context.get("pending_requests", []) or [] if isinstance(saved, dict)
                 and all(saved.get(field) == request.get(field) for field in fields)), None)


def _request_evidence(context, request):
    if not isinstance(request, dict) or request.get("intent") != "place_details" or not request.get("request_id"):
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
    if message and (message.get("author_id") != owner or quote not in message.get("text", "")):
        return None
    ids, quotes = [source], [quote]
    for item in request.get("context_evidence", []):
        mid, text, author = item.get("message_id"), item.get("quote"), item.get("author_id")
        original = known.get(mid)
        if author != owner or not isinstance(text, str) or not text:
            return None
        if original is None and saved is None:
            return None
        if original and (original.get("author_id") != author or text not in original.get("text", "")):
            return None
        ids.append(mid)
        quotes.append(text)
    return _unique(ids), quotes, saved


def _request_places(context):
    places, sources, observations = {}, {}, []
    room = context.get("room_id")
    for observation in context["observations"]:
        if observation.get("tool_name") not in ("search_places", "get_place_details"):
            continue
        result = observation.get("result", {})
        if observation.get("room_id", room) != room or result.get("room_id", room) != room:
            continue
        if result.get("place", {}).get("room_id", room) != room:
            continue
        observations.append(observation)
        proof = _unique([observation.get("id"), observation.get("observation_id")] + observation.get("source_refs", []))
        for place in result.get("places", []) + ([result["place"]] if result.get("place") else []):
            if place.get("room_id", room) != room or not place.get("id"):
                continue
            ref = place["id"]
            places[ref] = place
            sources[ref] = _unique(sources.get(ref, []) + proof + [place.get("source_ref")])
    return places, sources, observations


def _request_tool_candidates(context, requests):
    """Resolve semantic detail requests through observed refs, with no planning fallback."""
    if not isinstance(requests, list):
        return []
    places, sources, observations = _request_places(context)
    execution_context = dict(context, places=places, observations=observations)
    candidates = []
    current_order = {m["id"]: index for index, m in enumerate(context["recent_messages"])}
    ordered = sorted(enumerate(requests), key=lambda pair: (current_order.get(
        pair[1].get("source_message_id") if isinstance(pair[1], dict) else None, len(current_order)), pair[0]))
    for _, request in ordered:
        provenance = _request_evidence(context, request)
        if provenance is None or request.get("status") != "resolved":
            continue
        ids, quotes, saved = provenance
        excluded = set(request.get("excluded_refs", []))
        refs = request.get("target_refs", [])
        names = request.get("target_names", [])
        if not isinstance(refs, list) or not isinstance(names, list) or len(refs) != len(names):
            continue
        def target_position(pair):
            name = pair[1]
            if isinstance(name, str) and name:
                for order, quote in enumerate(quotes):
                    at = normalized(quote).find(normalized(name))
                    if at >= 0:
                        return order, at
            return len(quotes), 0
        for ref, name in sorted(zip(refs, names), key=target_position):
            if not isinstance(name, str) or not name or ref in excluded or ref not in places:
                continue
            if normalized(places[ref].get("name", "")) != normalized(name):
                continue
            if not any(normalized(name) in normalized(text) for text in quotes):
                continue
            if saved is not None and (ref in saved.get("completed_refs", [])
                                      or "pending_refs" in saved and ref not in saved["pending_refs"]):
                continue
            arguments = dict(place_ref=ref)
            try:
                validate_arguments("get_place_details", arguments, execution_context)
            except _ERRORS:
                continue
            if any(o.get("tool_name") == "get_place_details" and o.get("arguments") == arguments for o in observations):
                continue
            existing = next((c for c in candidates if c["arguments"] == arguments), None)
            proof = _unique([ref] + sources.get(ref, []))
            if existing:
                existing["request_ids"] = _unique(existing["request_ids"] + [request["request_id"]])
                existing["source_message_ids"] = _unique(existing["source_message_ids"] + ids)
                existing["source_refs"] = _unique(existing["source_refs"] + proof)
            else:
                value = _candidate("tool", "현재 요청에서 선택한 장소의 상세 정보를 조회합니다.", arguments,
                                   "get_place_details", ids, proof)
                value["request_ids"] = [request["request_id"]]
                candidates.append(value)
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


def _grounded_direct(context, text, ids):
    if any(text in _messages(context)[mid].get("text", "") for mid in ids):
        return True
    # A standalone confirmed scalar is safe; free-form paraphrases remain with the helper.
    values = [c.get("value") for c in context["constraints"] if c.get("status") == "confirmed"]
    values.extend(v for v in context["config"].values() if isinstance(v, (str, int, float, bool)))
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
        return any(i.get("id") == ref and _eligible(i) for i in context["items"])
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
    if analysis.get("noop") is True and not requests:
        return dict(branch="noop", candidates=[])
    context = _context(task)
    calls = _request_tool_candidates(context, requests) if requests else _tool_candidates(context)
    ids = _analysis_sources(task, analysis)
    source_refs = analysis.get("source_refs", [])
    if not isinstance(source_refs, list) or not set(source_refs) <= _known_refs(context):
        ids = None
    unsupported = []
    service_limit = canonical_unsupported(context)
    if service_limit["unsupported"]:
        unsupported = [_candidate("unsupported", service_limit["unsupported_reason"],
            message_ids=service_limit["source_message_ids"], refs=service_limit["source_refs"])]
    if calls:
        prepared = dict(branch="valid", candidates=calls[:3] + unsupported)
        if len(calls) > 3:
            prepared["deferred_candidates"] = calls[3:]
        return prepared
    candidates = ([] if requests else _missing_questions(context, analysis)) + unsupported
    text = analysis.get("direct_text")
    if not requests and isinstance(text, str) and text.strip() and ids and _grounded_direct(context, text, ids):
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
                    "target_names", "excluded_names", "target_refs", "excluded_refs", "context_evidence", "status"))
                                  for request in requests]} if analysis.get("requests") else {}))
