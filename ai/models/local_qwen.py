import json
from ai.models.qwen_loader import load_components
from ai.models.qwen_generation import generate_object
from ai.tools.definitions import TOOL_DEFINITIONS
from ai.context import model_context


def score_objects(model, tokenizer, context, candidates):
    from submission.judge import judge_scores
    choices = [("<tool_call>" + json.dumps(dict(name=c["tool_name"], arguments=c["arguments"]), ensure_ascii=False)
                + "</tool_call>") if c["action"] == "tool" else c["reason"] for c in candidates]
    return judge_scores(model, tokenizer, json.dumps(context, ensure_ascii=False), TOOL_DEFINITIONS, choices)


class LocalQwenBackend:
    mode = "local_qwen"

    def __init__(self, base_path, adapter_path):
        self.model, self.tokenizer = load_components(base_path, adapter_path)

    def generate_json(self, request):
        with self.model.disable_adapter():
            return generate_object(self.model, self.tokenizer, dict(request, context=model_context(request.get("context", {}))))

    def score_candidates(self, context, candidates):
        return score_objects(self.model, self.tokenizer, model_context(context), candidates)

    def close(self):
        self.model, self.tokenizer = None, None
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
