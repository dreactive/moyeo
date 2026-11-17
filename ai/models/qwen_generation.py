import json
from pathlib import Path


def generate_object(model, tokenizer, request):
    phase = "extract" if request["phase"] == "extract" else "generate"
    system = (Path(__file__).parents[1] / "prompts" / (phase + ".txt")).read_text(encoding="utf-8")
    prompt = tokenizer.apply_chat_template([dict(role="system", content=system),
             dict(role="user", content=json.dumps(request["context"], ensure_ascii=False))],
             tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    length = inputs["input_ids"].shape[1]
    if length > 24000:
        raise ValueError("Grounded input exceeds local context budget")
    import torch
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=1536, do_sample=False,
                                pad_token_id=tokenizer.eos_token_id)
    return parse_object(tokenizer.decode(output[0][length:], skip_special_tokens=True))


def parse_object(text):
    text = text.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("Model output must be one JSON object")
    return value
