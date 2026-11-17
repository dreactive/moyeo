def question(field, target_ref, text, owner_id=None, related_item_ids=None):
    return dict(id=f"question:{field}:{target_ref}", owner_id=owner_id, field=field,
                target_ref=target_ref, text=text, related_item_ids=related_item_ids or [],
                status="open", answer=None, answered_by=None)


def valid_questions(task, questions, proposals=()):
    items = {i["id"] for i in task.get("items", [])} | {i["client_ref"] for i in proposals}
    constraints = {c["id"]: c for c in task.get("constraints", [])}
    accepted = []
    for q in questions:
        field, ref = q["field"], q.get("target_ref")
        valid = field in ("origin", "destination", "lodging") and ref == "anchor:" + field
        valid |= field in ("menu_selection", "visit_duration") and ref in items
        valid |= field == "constraint_value" and ref in constraints and q["owner_id"] == constraints[ref]["owner_id"]
        valid |= field == "support_target" and q["id"].startswith("question:support_target:") and q["owner_id"] is not None
        if valid and q not in accepted:
            accepted.append(q)
    return accepted
