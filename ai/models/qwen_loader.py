from pathlib import Path


def load_components(base_path, adapter_path):
    base, adapter = Path(base_path or ""), Path(adapter_path or "")
    adapter = adapter.parent if adapter.is_file() else adapter
    if not (base / "config.json").is_file() or not (adapter / "adapter_model.safetensors").is_file():
        raise ValueError("Complete local base and adapter paths required; no downloads")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tokenizer = AutoTokenizer.from_pretrained(str(base), local_files_only=True, trust_remote_code=False)
    model = AutoModelForCausalLM.from_pretrained(str(base), local_files_only=True, trust_remote_code=False,
                torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32, attn_implementation="sdpa")
    model = PeftModel.from_pretrained(model, str(adapter), is_trainable=False, local_files_only=True)
    return model.to(device).eval(), tokenizer
