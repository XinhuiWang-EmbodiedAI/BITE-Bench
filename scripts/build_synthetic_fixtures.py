"""Create five explicitly synthetic foods, two menus and two users."""

import csv
import json
from pathlib import Path

from bitebench.core.schemas import DayPlan, FoodVariant

out = Path("data/fixtures/synthetic")
out.mkdir(parents=True, exist_ok=True)
foods = []
for i, category in enumerate(
    ["staple", "meat_egg", "vegetable_legume", "fruit", "beverage"], 1
):
    foods.append(
        FoodVariant(
            food_id=f"demo_f{i}",
            name_zh=f"合成食物{i}",
            primary_category=category,
            recipe_variant="synthetic_fixture_v1",
            serving_g=200,
            energy_kcal_per_100g=120,
            protein_g_per_100g=5,
            fat_g_per_100g=2,
            carbs_g_per_100g=20,
            fiber_g_per_100g=3,
            sodium_mg_per_100g=100,
            fruit_veg_g_per_serving=100,
            source_system="synthetic_fixture",
            data_quality="unknown",
            is_synthetic=True,
        ).model_dump()
    )
with (out / "foods.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(foods[0]))
    writer.writeheader()
    writer.writerows(foods)
menus = [
    DayPlan(
        menu_id=f"demo_day_0{i}",
        profile_id="balanced",
        is_synthetic=True,
        meals=[
            {
                "meal_id": f"demo_meal_{i}",
                "slot": "lunch",
                "items": [{"food_id": f"demo_f{i}", "servings": 1}],
            }
        ],
    ).model_dump()
    for i in (1, 2)
]
(out / "menus.json").write_text(json.dumps(menus, ensure_ascii=False, indent=2) + "\n")
(out / "users.json").write_text(
    json.dumps(
        [{"user_id": f"demo_u{i}", "is_synthetic": True} for i in (1, 2)], indent=2
    )
    + "\n"
)
print("SYNTHETIC DEMO: wrote 5 foods, 2 menus, 2 users; no human observations.")
