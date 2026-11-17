# Copyright (c) 2025 NVIDIA CORPORATION. All rights reserved.
# Qwen prompt adapted from NVIDIA When2Call under Apache-2.0.
"""Default Qwen/LoRA inference helpers; teams may replace this implementation.

Only the JSON input/output contract is shared. This helper does not prescribe
the architecture of an auxiliary model or require teams to use its scorer.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

SYSTEM = '''You are Qwen, created by Alibaba Cloud. You are a helpful assistant.

# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{tools}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{{"name": <function-name>, "arguments": <args-json-object>}}
</tool_call>'''


def validate_item(item):
    if not isinstance(item, dict) or set(item) != {'question', 'tools', 'choices'}:
        raise ValueError('Input must contain exactly question, tools and choices')
    if not isinstance(item['question'], str) or not item['question'].strip():
        raise ValueError('question must be nonempty text')
    if not isinstance(item['tools'], list):
        raise ValueError('tools must be a list')
    for tool in item['tools']:
        if isinstance(tool, str):
            tool = json.loads(tool)
        if not isinstance(tool, dict):
            raise ValueError('Each tool must be an object or JSON object string')
    if (not isinstance(item['choices'], list) or len(item['choices']) != 4
            or any(not isinstance(choice, str) or not choice.strip() for choice in item['choices'])):
        raise ValueError('choices must contain four nonempty texts')
    return item


def prompt_for(item):
    validate_item(item)
    tools = '\n'.join(tool if isinstance(tool, str) else json.dumps(tool, ensure_ascii=False)
                      for tool in item['tools']).strip()
    return ('<|im_start|>system\n' + SYSTEM.format(tools=tools) + '<|im_end|>\n'
            '<|im_start|>user\n' + item['question'] + '<|im_end|>\n<|im_start|>assistant\n')


def encode_pair(tokenizer, context, continuation):
    """Match lm-evaluation-harness causal pair tokenization exactly."""
    trailing = len(context) - len(context.rstrip())
    if trailing:
        continuation = context[-trailing:] + continuation
        context = context[:-trailing]
    context_tokens = tokenizer.encode(context, add_special_tokens=False)
    whole_tokens = tokenizer.encode(context + continuation, add_special_tokens=False)
    continuation_tokens = whole_tokens[len(context_tokens):]
    if not context_tokens or not continuation_tokens:
        raise ValueError('Prompt and candidate must each contain at least one token')
    return context_tokens, continuation_tokens


def raw_scores(model, tokenizer, item, max_length=32768):
    import torch
    import torch.nn.functional as functional
    prompt = prompt_for(item)
    maximum = min(max_length, getattr(model.config, 'max_position_embeddings', max_length))
    scores = []
    with torch.inference_mode():
        for choice in item['choices']:
            context, continuation = encode_pair(tokenizer, prompt, choice)
            if len(continuation) > maximum:
                raise ValueError('Candidate is longer than the model context window')
            tokens = (context + continuation)[-(maximum + 1):][:-1]
            inputs = torch.tensor([tokens], dtype=torch.long, device=model.device)
            # Batch one, no padding: this matches the original HF scorer call.
            output = model(input_ids=inputs,use_cache=False)
            # Only candidate positions contribute to this score. Release the
            # full prompt logits before softmax and before the next candidate.
            # clone() avoids a small view retaining the full large allocation.
            candidate_logits = output.logits[:, -len(continuation):, :].clone()
            del output
            selected = functional.log_softmax(candidate_logits, dim=-1, dtype=torch.float32)
            targets = torch.tensor([continuation], dtype=torch.long, device=model.device)
            value = float(torch.gather(selected, 2, targets.unsqueeze(-1)).squeeze(-1).sum())
            if not math.isfinite(value):
                raise ValueError('Model returned a nonfinite candidate score')
            scores.append(value)
            del candidate_logits, selected, targets, inputs
    return scores


def load_default(package_dir=None):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    folder = Path(package_dir or Path(__file__).parent).resolve()
    weights = folder / 'weights'
    base = Path(os.environ.get('ARENA_BASE_MODEL', '/opt/arena/base_model'))
    device = os.environ.get('ARENA_DEVICE', 'cuda')
    dtype_name = os.environ.get('ARENA_DTYPE', 'bfloat16' if device.startswith('cuda') else 'float32')
    if dtype_name not in ('float32', 'bfloat16', 'float16'):
        raise ValueError('ARENA_DTYPE must be float32, bfloat16 or float16')
    dtype = getattr(torch, dtype_name)
    if device.startswith('cuda') and not torch.cuda.is_available():
        raise ValueError('CUDA is unavailable; use ARENA_DEVICE=cpu for a local CPU check')
    tokenizer = AutoTokenizer.from_pretrained(str(base), local_files_only=True, trust_remote_code=False)
    adapter_files = [weights / 'adapter_config.json', weights / 'adapter_model.safetensors']
    full = weights / 'model.safetensors'
    if full.is_file() and any(path.exists() for path in adapter_files):
        raise ValueError('Default helper expects one model format; customize inference.py for a combined system')
    if any(path.exists() for path in adapter_files) and not all(path.is_file() for path in adapter_files):
        raise ValueError('LoRA requires both adapter_config.json and adapter_model.safetensors')
    options = {'torch_dtype': dtype, 'attn_implementation': 'sdpa',
               'local_files_only': True, 'trust_remote_code': False}
    if full.is_file():
        from safetensors.torch import load_file
        config = AutoConfig.from_pretrained(str(base), local_files_only=True, trust_remote_code=False)
        model = AutoModelForCausalLM.from_pretrained(None, config=config,
            state_dict=load_file(str(full)), **options)
    else:
        model = AutoModelForCausalLM.from_pretrained(str(base), **options)
        if all(path.is_file() for path in adapter_files):
            from peft import PeftModel
            model = PeftModel.from_pretrained(model, str(weights), is_trainable=False, local_files_only=True)
        elif any(path.is_file() and path.name != 'README.md' for path in weights.rglob('*')):
            raise ValueError('Custom weights require matching loading code in inference.py')
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    return model.to(device).eval(), tokenizer


class DefaultPredictor:
    def __init__(self, package_dir=None):
        self.model, self.tokenizer = load_default(package_dir)

    def predict(self, item):
        scores = raw_scores(self.model, self.tokenizer, item)
        return {'choice_index': int(max(range(4), key=scores.__getitem__))}
