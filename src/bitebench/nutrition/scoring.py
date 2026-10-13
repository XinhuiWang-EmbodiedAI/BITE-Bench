"""Fixed mathematical scoring primitives, following playbook E.2."""

import math

COMPONENTS = ("taste", "nutrition", "fitness", "long_term")


def validate_weights(weights: dict[str, float]) -> None:
    if set(weights) != set(COMPONENTS):
        raise ValueError("exactly four named component weights are required")
    if any(not math.isfinite(v) or v < 0 for v in weights.values()):
        raise ValueError("weights must be finite and nonnegative")
    if not math.isclose(sum(weights.values()), 1, abs_tol=1e-9):
        raise ValueError("weights must sum to one")


def aggregate(
    scores: dict[str, float],
    weights: dict[str, float],
    eligibility: str,
    penalty: float = 0,
) -> dict:
    validate_weights(weights)
    if eligibility in {"ineligible", "insufficient_data"}:
        return {"eligibility": eligibility, "total_0_100": None}
    if eligibility != "eligible":
        raise ValueError("invalid eligibility")
    if set(scores) != set(COMPONENTS) or any(
        not math.isfinite(v) or not 0 <= v <= 100 for v in scores.values()
    ):
        raise ValueError("all four scores must be finite and within [0,100]")
    if not math.isfinite(penalty) or penalty < 0:
        raise ValueError("invalid penalty")
    return {
        "eligibility": eligibility,
        "q_t": scores["taste"],
        "q_n": scores["nutrition"],
        "q_f": scores["fitness"],
        "q_l": scores["long_term"],
        "total_0_100": min(
            100, max(0, sum(scores[k] * weights[k] for k in COMPONENTS) - penalty)
        ),
    }
