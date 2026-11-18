import json
from pathlib import Path
from ai.context import extraction_context


def generate_object(model, tokenizer, request):
    phase = "extract" if request["phase"] == "extract" else "generate"
    system = (Path(__file__).parents[1] / "prompts" / (phase + ".txt")).read_text(encoding="utf-8")
    if phase == "extract":
        from ai.extraction_schema import MessageFacts
        system += "\nJSON Schema: " + json.dumps(MessageFacts.model_json_schema(), ensure_ascii=False)
    if request.get("validation_error"):
        system += "\n이전 구조 검증이 실패했습니다. 필수 필드와 JSON 완결성을 지키세요: " + request["validation_error"]
    context = extraction_context(request["context"]) if phase == "extract" else request["context"]
    prompt = tokenizer.apply_chat_template([dict(role="system", content=system),
             dict(role="user", content=context["recent_messages"][0]["text"] if phase == "extract" and context["recent_messages"] else json.dumps(context, ensure_ascii=False))],
             tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    length = inputs["input_ids"].shape[1]
    if length > 24000:
        raise ValueError("Grounded input exceeds local context budget")
    import torch
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=1536, do_sample=False,
                                pad_token_id=tokenizer.eos_token_id, **extraction_options(request, tokenizer))
    return parse_object(tokenizer.decode(output[0][length:], skip_special_tokens=True))


def parse_object(text):
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Model output must be one JSON object")
    return value


def extraction_options(request, tokenizer):
    if request['phase'] != 'extract':
        return {}
    from ai.extraction_schema import MessageFacts
    from ai.models.structured_generation import build_extraction_prefix
    return dict(prefix_allowed_tokens_fn=build_extraction_prefix(tokenizer, MessageFacts.model_json_schema(), json.dumps(request.get("context", {}), ensure_ascii=False)))
