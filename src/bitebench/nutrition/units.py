"""Unit conversions only; salt and sodium are distinct quantities."""

import math


def convert(value: float | None, source_unit: str, target_unit: str) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value) or value < 0:
        raise ValueError("nutrient amounts must be finite and nonnegative")
    source, target = source_unit.strip().lower(), target_unit.lower()
    if source == target and source in {"g", "mg", "kcal", "kj"}:
        return value
    factors = {
        ("mg", "g"): 0.001,
        ("g", "mg"): 1000,
        ("kj", "kcal"): 1 / 4.184,
        ("kcal", "kj"): 4.184,
    }
    if (source, target) not in factors:
        raise ValueError("unsupported unit conversion")
    return value * factors[source, target]


def salt_to_sodium_mg(salt_g: float | None) -> float | None:
    # Explicit approximate composition conversion, never a rename of salt_g.
    return None if salt_g is None else convert(salt_g, "g", "mg") / 2.5


def per_serving_to_100g(value: float | None, serving_g: float) -> float | None:
    if not math.isfinite(serving_g) or serving_g <= 0:
        raise ValueError("serving mass must be finite and positive")
    if value is None:
        return None
    if not math.isfinite(value) or value < 0:
        raise ValueError("invalid nutrient amount")
    return value * 100 / serving_g
