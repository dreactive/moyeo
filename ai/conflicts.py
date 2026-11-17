def conflict(kind, text, item_ids, versions):
    return dict(id=f"conflict:{kind}:{':'.join(item_ids)}", type=kind, explanation=text,
                affected_item_ids=item_ids, base_versions=versions, blocking=True, status="open",
                options=[dict(id=f"drop:{item}", label="방문 제외", effect_summary="이 방문을 제외하고 재계산",
                              requires_owner_id=None, effect=dict(kind="drop_visit", item_id=item))
                         for item in item_ids])
