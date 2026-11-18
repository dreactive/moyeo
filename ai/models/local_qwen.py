from ai.models.qwen_loader import load_components
from ai.models.qwen_generation import generate_object
from ai.context import model_context


class LocalQwenBackend:
    mode = "local_qwen"

    def __init__(self, base_path, adapter_path):
        self.model, self.tokenizer = load_components(base_path, adapter_path)

    def generate_json(self, request):
        with self.model.disable_adapter():
            if request.get("phase") == "extract":
                from ai.models.qwen_extraction import generate_extraction
                return generate_extraction(self.model, self.tokenizer, request)
            return generate_object(self.model, self.tokenizer, dict(request, context=model_context(request.get("context", {}))))

    def score_candidates(self, context: dict, candidates: list[dict]) -> list[float]:
        from ai.models.qwen_judge import score_candidates
        return score_candidates(self.model, self.tokenizer, context, candidates)

    def close(self):
        self.model, self.tokenizer = None, None
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
