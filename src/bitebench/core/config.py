"""Load draft rubric weights with strict numeric validation."""

import math
from pathlib import Path

import yaml

from bitebench.nutrition.scoring import validate_weights


def load_rubric(path: Path) -> dict:
    value = yaml.safe_load(path.read_text())
    for weights in value["profiles"].values():
        validate_weights(weights)
    for target in value["reference_goals"].values():
        if (
            not isinstance(target, (int, float))
            or not math.isfinite(target)
            or target <= 0
        ):
            raise ValueError("reference goals must be positive")
    return value
