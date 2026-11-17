"""Deterministic fixture model. Never reports real Qwen quality."""
import re


class FakeModelBackend:
    mode = "fake"

    def generate_json(self, request):
        context = request["context"]
        output = dict(constraint_proposals=[], item_proposals=[], support_observations=[])
        for message in context["recent_messages"]:
            budget = re.search(r"(\d+)만원", message["text"])
            if budget:
                old = next((c["id"] for c in context["constraints"] if c["owner_id"] == message["author_id"]
                            and c["key"] == "budget"), None)
                output["constraint_proposals"].append(dict(owner_id=message["author_id"], key="budget",
                    value=int(budget[1]) * 10000, kind="hard", source_message_ids=[message["id"]],
                    replaces_constraint_id=old))
            for item in context["items"]:
                if item["title"].split()[-1] in message["text"]:
                    stance = "withdraw" if "철회" in message["text"] else "oppose" if "반대" in message["text"] else "support"
                    output["support_observations"].append(dict(item_id=item["id"], item_version=item["item_version"],
                        author_id=message["author_id"], stance=stance, source_message_id=message["id"]))
        return output

    def score_candidates(self, context, candidates):
        return [float(len(candidates) - i) for i in range(len(candidates))]
