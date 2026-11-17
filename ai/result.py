"""Only proposals cross the runtime boundary."""


def empty_result(task):
    result = {key: task[key] for key in ("run_id", "room_id", "base_versions")}
    for key in ("constraint_proposals", "support_observations", "item_proposals",
                "observations", "conflicts", "questions"):
        result[key] = []
    result.update(plan_draft=None, completion="needs_input",
                  last_processed_message_id=next(
                      (m["id"] for m in reversed(task["recent_messages"])), None))
    return result
