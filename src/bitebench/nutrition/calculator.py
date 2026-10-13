"""Deterministic portion arithmetic, with explicit missing propagation."""

import math

from bitebench.core.schemas import DayPlan, FoodVariant

NUTRIENTS = ("energy_kcal", "protein_g", "fat_g", "carbs_g", "fiber_g", "sodium_mg")
REQUIRED = ("energy_kcal", "protein_g", "fiber_g", "sodium_mg", "fruit_veg_g")


def portion(food: FoodVariant, servings: float) -> dict:
    if not math.isfinite(servings) or servings <= 0:
        raise ValueError("servings must be positive")
    result = {}
    for name in NUTRIENTS:
        value = getattr(food, name + "_per_100g")
        result[name] = (
            None if value is None else value * food.serving_g * servings / 100
        )
    result["fruit_veg_g"] = (
        None
        if food.fruit_veg_g_per_serving is None
        else food.fruit_veg_g_per_serving * servings
    )
    return result


def calculate_day(
    menu: DayPlan, foods: dict[str, FoodVariant], allow_synthetic: bool = False
) -> dict:
    if menu.is_synthetic and not allow_synthetic:
        raise ValueError("synthetic menus are forbidden in formal scoring")
    parts = []
    for meal in menu.meals:
        for item in meal.items:
            if item.food_id not in foods:
                raise ValueError(f"unknown food_id: {item.food_id}")
            food = foods[item.food_id]
            if food.is_synthetic and not allow_synthetic:
                raise ValueError("synthetic foods are forbidden in formal scoring")
            parts.append(portion(food, item.servings))
    total = {
        name: None
        if any(p[name] is None for p in parts)
        else sum(p[name] for p in parts)
        for name in (*NUTRIENTS, "fruit_veg_g")
    }
    missing = [name for name in REQUIRED if total[name] is None]
    return {
        "totals": total,
        "unknown_fields": missing,
        "eligibility": "insufficient_data" if missing else "eligible",
        "is_synthetic": menu.is_synthetic
        or any(
            foods[item.food_id].is_synthetic
            for meal in menu.meals
            for item in meal.items
        ),
    }
