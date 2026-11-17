def question(field, target_ref, text, owner_id=None, related_item_ids=None):
    return dict(id=f"question:{field}:{target_ref}", owner_id=owner_id, field=field,
                target_ref=target_ref, text=text, related_item_ids=related_item_ids or [],
                status="open", answer=None, answered_by=None)
