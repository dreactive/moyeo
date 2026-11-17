"""Common JSONL entry point. Replace Predictor to attach any auxiliary model.

The organizer supplies ARENA_BASE_MODEL. Runtime stdout must contain only one
{"choice_index": 0..3} object for every input line; send logs to stderr.
"""
from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
import sys


def main():
    if '--help' in sys.argv:
        print(__doc__)
        return 0
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('HF_DATASETS_OFFLINE', '1')
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from team_predictor import TeamPredictor
            predictor = TeamPredictor(Path(__file__).resolve().parent)
        for line in sys.stdin:
            if not line.strip():
                continue
            if len(line.encode('utf-8')) > 1024 * 1024:
                raise ValueError('Input exceeds 1 MiB')
            item = json.loads(line)
            with contextlib.redirect_stdout(sys.stderr):
                result = predictor.predict(item)
            if (not isinstance(result, dict) or set(result) != {'choice_index'}
                    or type(result['choice_index']) is not int or not 0 <= result['choice_index'] < 4):
                raise ValueError('Output must be exactly {"choice_index": integer 0..3}')
            print(json.dumps(result, allow_nan=False), flush=True)
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
