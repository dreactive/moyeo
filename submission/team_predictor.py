"""Team predictor: organizer default scorer + tool-schema rule filter (rules.py).

Scoring: the kit scorer (summed log-prob of each choice). If weights/ref/ holds a second LoRA
(the SFT adapter the DPO policy in weights/ was trained from), each choice is scored with both
adapters on the same base model and the choice is made on log P_policy - log P_ref, the
implicit DPO reward. The rule filter is then applied to these finite scores.

If scorer.json says {"scorer": "judge"}, the LoRA in weights/ is a yes/no judge (judge.py,
tools/train_judge.py) and each choice is scored by logit(yes) - logit(no) after the question
"was your previous reply right?". Without scorer.json the package behaves as before.

Rule: a candidate that is a tool call (raw JSON with "name"/"arguments") is
excluded when the request provides no tools or the call names a tool that is
not in the provided list. If every candidate were excluded, the scores are
used unchanged. tools/local_eval.py imports the same rules.py.

A failure on one request must not end the whole run (inference.py exits on any
exception), so problems are logged to stderr and a valid index is still returned.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from rules import apply_rules
from runtime_helpers import load_default, raw_scores, validate_item


def _load_second_adapter(model, folder, name):
    """peft 0.15.2 load_adapter on a bf16 base rounds the new adapter's weights to bf16 before
    upcasting them to fp32 (the first adapter keeps exact fp32). Copy the exact values back so the
    second adapter scores exactly like that adapter loaded on its own."""
    from peft.utils import set_peft_model_state_dict
    from safetensors.torch import load_file
    model.load_adapter(str(folder), adapter_name=name, is_trainable=False)
    result = set_peft_model_state_dict(model, load_file(str(folder / 'adapter_model.safetensors')), adapter_name=name)
    if result.unexpected_keys:
        raise ValueError(f'adapter {name}: {len(result.unexpected_keys)} unexpected keys')


class TeamPredictor:
    def __init__(self, package_dir=None):
        self.model, self.tokenizer = load_default(package_dir)
        folder = Path(package_dir or Path(__file__).parent).resolve()
        config = folder / 'scorer.json'
        self.scorer = json.loads(config.read_text(encoding='utf-8'))['scorer'] if config.is_file() else 'logprob'
        if self.scorer not in ('logprob', 'judge'):
            raise ValueError(f'unknown scorer {self.scorer!r} in scorer.json')
        if self.scorer == 'judge':
            from judge import direction
            self.direction = direction(self.model, self.tokenizer)
        ref = folder / 'weights' / 'ref'
        self.has_ref = (ref / 'adapter_config.json').is_file() and (ref / 'adapter_model.safetensors').is_file()
        if self.has_ref and self.scorer == 'judge':
            raise ValueError('a judge package must not contain weights/ref')
        if self.has_ref:
            _load_second_adapter(self.model, ref, 'ref')
            self.model.set_adapter('default')
            self.model.eval()

    def _reference_scores(self, item):
        self.model.set_adapter('ref')
        try:
            return raw_scores(self.model, self.tokenizer, item)
        finally:
            self.model.set_adapter('default')

    def selection_scores(self, item):
        """(scores the choice is made on before the rule filter, policy scores, reference scores or None)."""
        if self.scorer == 'judge':
            from judge import judge_scores
            z = judge_scores(self.model, self.tokenizer, item['question'], item['tools'], item['choices'], self.direction)
            return z, z, None
        policy = raw_scores(self.model, self.tokenizer, item)
        if not self.has_ref:
            return policy, policy, None
        ref = self._reference_scores(item)
        return [p - r for p, r in zip(policy, ref)], policy, ref

    def predict(self, item):
        validate_item(item)
        try:
            scores = self.selection_scores(item)[0]
        except Exception as error:  # e.g. CUDA OOM on an extreme input
            print(f'scoring failed: {type(error).__name__}: {error}', file=sys.stderr)
            try:
                self.model.set_adapter('default') if self.has_ref else None
                scores = raw_scores(self.model, self.tokenizer, item)
                print('using policy scores only for this item', file=sys.stderr)
            except Exception as error2:
                print(f'policy scoring failed too, answering 0: {type(error2).__name__}: {error2}', file=sys.stderr)
                return {'choice_index': 0}
        try:
            final = apply_rules(scores, item['choices'], item['tools'])
        except Exception as error:
            print(f'rules skipped: {type(error).__name__}: {error}', file=sys.stderr)
            final = scores
        return {'choice_index': int(max(range(4), key=final.__getitem__))}
