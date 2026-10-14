"""Training-only candidate access; never accepts test labels."""

import math

from bitebench.labeling.protocol import audit


def training_pool(protocol: dict, answered_pair_ids=()) -> list[dict]:
    audit(protocol)
    answered = set(answered_pair_ids)
    return [
        dict(p)
        for p in protocol["pairs"]
        if p["split"] == "train" and p["pair_id"] not in answered
    ]


def select_uncertain(protocol: dict, probabilities: dict, answered_pair_ids=()) -> dict:
    pool = training_pool(protocol, answered_pair_ids)
    if not pool:
        raise ValueError("no training candidates remain")
    allowed = {p["pair_id"] for p in pool}
    if set(probabilities) != allowed:
        raise ValueError("probabilities must cover training candidates only")
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities.values()):
        raise ValueError("invalid probabilities")
    return min(
        pool,
        key=lambda item: (
            -probabilities[item["pair_id"]] * (1 - probabilities[item["pair_id"]]),
            item["pair_id"],
        ),
    )
