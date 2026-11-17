"""Yes/no judge: score each choice by how strongly the model says the reply was right.

The judge reads the kit's tool prompt and the user's question, sees one candidate as the
assistant's reply, and is then asked whether that reply was right. Its score is
    z = logit('yes') - logit('no')
at the position where the answer would start. That is one dot product of the final hidden
state with the difference of the two output-embedding rows, done in fp32. Training
(tools/train_judge.py), local evaluation and the submission package all use this file, so
the prompt and the score are the same everywhere.

Unlike the kit scorer, a long candidate is not penalised for having more tokens: the
candidate is input, and only the yes/no position is scored.
"""
from __future__ import annotations

import json
import math

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

INSTRUCTION = ('Check your previous reply against the user request and the tools listed in the system message. '
               'A right reply calls a listed tool only when that tool can do the task and every required '
               'argument is known from the request; asks the user for the missing details when a listed tool '
               'fits but required information is missing; and says it cannot help when no listed tool can do '
               'the task. A reply that answers directly with made-up results is wrong. '
               'Was your previous reply right? Answer yes or no.')


def tool_text(tools):
    return '\n'.join(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False) for t in tools).strip()


def judge_prompt(question, tools, candidate):
    return ('<|im_start|>system\n' + SYSTEM.format(tools=tool_text(tools)) + '<|im_end|>\n'
            '<|im_start|>user\n' + question + '<|im_end|>\n'
            '<|im_start|>assistant\n' + candidate.strip() + '<|im_end|>\n'
            '<|im_start|>user\n' + INSTRUCTION + '<|im_end|>\n'
            '<|im_start|>assistant\n')


def answer_ids(tokenizer):
    ids = [tokenizer.encode(w, add_special_tokens=False) for w in ('yes', 'no')]
    if any(len(i) != 1 for i in ids):
        raise ValueError(f'yes/no are not single tokens: {ids}')
    return ids[0][0], ids[1][0]


def causal_lm(model):
    return model.get_base_model() if hasattr(model, 'get_base_model') else model


def direction(model, tokenizer):
    """fp32 vector d with z = h . d, from the (frozen) output embedding rows of yes and no."""
    yes, no = answer_ids(tokenizer)
    weight = causal_lm(model).get_output_embeddings().weight
    return (weight[yes].float() - weight[no].float()).detach()


def judge_scores(model, tokenizer, question, tools, choices, d=None, max_length=32768):
    """One forward per choice, batch one, no padding. Returns finite floats."""
    import torch
    causal = causal_lm(model)
    d = direction(model, tokenizer) if d is None else d
    maximum = min(max_length, getattr(causal.config, 'max_position_embeddings', max_length))
    scores = []
    with torch.inference_mode():
        for choice in choices:
            ids = tokenizer.encode(judge_prompt(question, tools, choice), add_special_tokens=False)[-maximum:]
            inputs = torch.tensor([ids], dtype=torch.long, device=d.device)
            hidden = causal.model(input_ids=inputs, use_cache=False).last_hidden_state[0, -1]
            value = float(hidden.float() @ d)
            if not math.isfinite(value):
                raise ValueError('judge returned a nonfinite score')
            scores.append(value)
            del hidden, inputs
    return scores
