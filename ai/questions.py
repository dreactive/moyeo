def question(field, target_ref, text, owner_id=None, related_item_ids=None):
    return dict(id=f"question:{field}:{target_ref}", owner_id=owner_id, field=field,
                target_ref=target_ref, text=text, related_item_ids=related_item_ids or [],
                status="open", answer=None, answered_by=None)


def valid_questions(task, questions, proposals=()):
    items = {i["id"] for i in task.get("items", [])} | {i["client_ref"] for i in proposals}
    constraints = {c["id"]: c for c in task.get("constraints", [])}
    members = {m["user_id"] for m in task.get("members", [])}
    requests = {r["request_id"]: r for r in (task.get("pending_requests") or []) + (task.get("_active_requests") or [])
                if isinstance(r, dict) and r.get("request_id")}
    accepted = []
    for q in questions:
        field, ref = q["field"], q.get("target_ref")
        valid = field in ("origin", "destination", "lodging") and ref == "anchor:" + field
        valid |= (field == "region" and ref == "config:region" and not task.get("config", {}).get("region")
                  and q.get("owner_id") in members | {None})
        valid |= field in ("menu_selection", "visit_duration") and ref in items
        valid |= field == "constraint_value" and ref in constraints and q["owner_id"] == constraints[ref]["owner_id"]
        valid |= field == "support_target" and q["id"].startswith("question:support_target:") and q["owner_id"] is not None
        valid |= field in ("target_places", "route_departure") and _valid_lookup_question(task, q, requests.get(ref, {}), members)
        if valid and q not in accepted:
            accepted.append(q)
    return accepted


def _valid_lookup_question(task, question, request, members):
    owner = question.get("owner_id")
    if not (owner and owner == request.get("owner_id") and owner in members
            and request.get("intent") in ("place_lookup", "place_details", "route_lookup")
            and request.get("status") not in ("cancelled", "superseded", "completed", "unsupported", "failed")
            and request.get("source_message_id") in question.get("source_message_ids", [])):
        return False
    if question["field"] == "route_departure":
        return request["intent"] == "route_lookup"
    target = question.get("target_name")
    if target and target not in request.get("target_names", []) + request.get("unresolved_target_names", []):
        return False
    places = {}
    for observation in task.get("observations", []):
        result = observation["result"]
        if observation["tool_name"] == "get_place_details" and result.get("place"):
            place = result["place"]
            places.setdefault(place["id"], place)
        if observation["tool_name"] == "search_places":
            places.update((p["id"], p) for p in result.get("places", []))
    for choice in question.get("place_choices", []):
        place = places.get(choice.get("place_ref")) if isinstance(choice, dict) else None
        if not place or choice.get("name") != place.get("name") or choice.get("address") != (place.get("address") or ""):
            return False
    return True
