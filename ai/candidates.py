import math


def select_candidate(candidates, scores):
    if not candidates or len(scores) != len(candidates):
        raise ValueError("Candidate score count mismatch")
    if any(isinstance(s, bool) or not isinstance(s, (float, int)) or not math.isfinite(s) for s in scores):
        raise ValueError("Nonfinite or invalid judge score")
    return max(range(len(candidates)), key=scores.__getitem__)
