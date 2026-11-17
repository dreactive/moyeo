def planned_visits(context):
    plan = context.get("current_plan") or {}
    refs = {i["id"]: i.get("place_ref") for i in plan.get("item_snapshots", [])}
    return [dict(item_id=v["item_id"], place_ref=refs.get(v["item_id"]) or v["place_ref"],
                 date=d["date"], preferred_start_at=v.get("start_at"),
                 stay_minutes=v.get("stay_minutes"), selected_menu_ids=v.get("selected_menu_ids", []))
            for d in plan.get("days", []) for v in d["visits"]]
