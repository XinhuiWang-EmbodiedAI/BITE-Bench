"""Mass-weighted recipe estimates with retained source and yield assumptions."""

import math
from datetime import datetime, timezone

from bitebench.core.hashing import content_hash
from bitebench.core.schemas import FoodVariant
from bitebench.data.normalization import FIELDS


def estimate_recipe(
    ingredients: list[tuple[FoodVariant, float]],
    yield_g: float,
    oil_salt_assumptions: str,
) -> dict:
    if not ingredients or not oil_salt_assumptions.strip():
        raise ValueError("ingredients and retained oil/salt assumptions are required")
    if not math.isfinite(yield_g) or yield_g <= 0:
        raise ValueError("finished edible yield must be finite and positive")
    for _, mass in ingredients:
        if not math.isfinite(mass) or mass <= 0:
            raise ValueError("ingredient edible masses must be finite and positive")
    nutrients = {}
    for field in FIELDS:
        values = [getattr(food, field) for food, _ in ingredients]
        nutrients[field] = (
            None
            if any(value is None for value in values)
            else sum(
                value * mass
                for value, (_, mass) in zip(values, ingredients, strict=True)
            )
            / yield_g
        )
    return {
        "nutrients": nutrients,
        "data_quality": "recipe_estimate",
        "method": "mass_weighted_finished_yield_v1",
        "yield_g": yield_g,
        "oil_salt_assumptions": oil_salt_assumptions,
        "fruit_veg_g_per_serving": None,
        "uncertainty_note": "Ingredient retention, raw/cooked basis and finished fruit/vegetable mass require review.",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "ingredients": [
            {
                "food_id": food.food_id,
                "edible_g": mass,
                "food_data_sha256": content_hash(food.model_dump()),
                "source_system": food.source_system,
                "source_record_id": food.source_record_id,
            }
            for food, mass in ingredients
        ],
        "is_synthetic": any(food.is_synthetic for food, _ in ingredients),
    }
