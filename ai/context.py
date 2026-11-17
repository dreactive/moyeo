from copy import deepcopy


def build_context(task, observations):
    context = deepcopy(task)
    context["recent_messages"] = context["recent_messages"][-20:]
    context["observations"] += deepcopy(observations)
    for q in context["questions"]:
        if q["status"] != "answered" or q.get("owner_id") not in (None, q.get("answered_by")):
            continue
        if q["field"] in ("origin", "destination", "lodging"):
            context["config"][q["field"]] = q["answer"]
    return context
