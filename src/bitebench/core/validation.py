"""Food table validation, without invented source values."""

import csv
from pathlib import Path

from bitebench.core.schemas import FoodVariant


def load_foods(path: Path, allow_synthetic: bool = False) -> dict[str, FoodVariant]:
    foods = {}
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            row = {
                key: None if value in {"", "null", "None"} else value
                for key, value in row.items()
            }
            food = FoodVariant.model_validate(row)
            if food.food_id in foods:
                raise ValueError(f"duplicate food_id: {food.food_id}")
            if food.is_synthetic and not allow_synthetic:
                raise ValueError("synthetic records require --allow-synthetic")
            foods[food.food_id] = food
    if not foods:
        raise ValueError("empty food table")
    return foods
