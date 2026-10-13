"""Stable binary preference likelihood; ties/skips are handled upstream."""

import math


def binary_pair_nll(logit: float, left_chosen: bool) -> float:
    if not math.isfinite(logit):
        raise ValueError("pair logit must be finite")
    return max(logit, 0) - logit * int(left_chosen) + math.log1p(math.exp(-abs(logit)))
