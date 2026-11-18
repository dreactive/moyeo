from copy import deepcopy


def model_context(value):
    if isinstance(value, dict):
        return {k: model_context(v) for k, v in value.items() if k not in ("polyline", "conversation_context")}
    if isinstance(value, list):
        return [model_context(v) for v in value]
    return value


def extraction_context(context):
    return dict(conversation_context=context.get("conversation_context", [])[-20:],
                reference_region=context.get("config", {}).get("region"), recent_messages=context.get("recent_messages", [])[-20:],
                members=context.get("members", []), questions=context.get("questions", []),
                constraints=context.get("constraints", []),
                items=[{k: i[k] for k in ("id", "item_version", "title")} for i in context.get("items", [])])


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
