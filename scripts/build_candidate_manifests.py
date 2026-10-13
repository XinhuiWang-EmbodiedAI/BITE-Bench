"""Draft identity-only candidates; never creates nutrition or approval data."""

import csv
import random
from pathlib import Path

from bitebench.core.schemas import FoodVariant
from bitebench.data.curation import csv_write
from bitebench.data.reviews import ReviewReceipt

GROUPS = {
    "staple": [
        ("白米饭", "white rice cooked", "cooked"),
        ("糙米饭", "brown rice cooked", "cooked"),
        ("全麦面包", "whole wheat bread", "labelled"),
        ("燕麦粥", "oatmeal cooked water", "cooked"),
        ("水煮面条", "noodles cooked", "cooked"),
        ("馒头", "steamed bread mantou", "composite"),
    ],
    "meat_egg": [
        ("烤鸡胸肉", "chicken breast roasted", "cooked"),
        ("水煮鸡蛋", "egg hard boiled", "cooked"),
        ("炖牛肉", "beef stewed", "cooked"),
        ("烤三文鱼", "salmon cooked", "cooked"),
        ("红烧肉", "braised pork belly", "composite"),
        ("炸鸡", "chicken fried", "composite"),
    ],
    "vegetable_legume": [
        ("生西兰花", "broccoli raw", "raw"),
        ("水煮菠菜", "spinach boiled", "cooked"),
        ("水煮胡萝卜", "carrots boiled", "cooked"),
        ("豆腐", "tofu firm", "labelled"),
        ("麻婆豆腐", "mapo tofu", "composite"),
        ("水煮卷心菜", "cabbage boiled", "cooked"),
    ],
    "fruit": [
        ("苹果", "apple raw", "raw"),
        ("香蕉", "banana raw", "raw"),
        ("橙子", "orange raw", "raw"),
        ("葡萄", "grapes raw", "raw"),
        ("西瓜", "watermelon raw", "raw"),
        ("梨", "pear raw", "raw"),
    ],
    "dessert": [
        ("香草冰淇淋", "vanilla ice cream", "labelled"),
        ("黑巧克力", "dark chocolate", "labelled"),
        ("芝士蛋糕", "cheesecake", "composite"),
        ("甜甜圈", "doughnut", "composite"),
        ("水果果冻", "fruit jelly", "labelled"),
        ("蛋挞", "egg tart", "composite"),
    ],
    "beverage": [
        ("饮用水", "drinking water", "labelled"),
        ("低脂牛奶", "milk 2 percent", "labelled"),
        ("原味豆浆", "soy beverage plain", "labelled"),
        ("含糖可乐", "cola regular", "labelled"),
        ("橙汁", "orange juice", "labelled"),
        ("珍珠奶茶", "bubble milk tea", "composite"),
    ],
    "fast_food": [
        ("汉堡薯条套餐", "burger fries meal", "composite"),
        ("鸡肉米饭套餐", "chicken rice meal", "composite"),
        ("披萨套餐", "pizza meal", "composite"),
        ("三明治套餐", "sandwich meal", "composite"),
        ("炸鸡套餐", "fried chicken meal", "composite"),
        ("热狗套餐", "hot dog meal", "composite"),
    ],
    "other": [
        ("猪肉饺子", "pork dumplings", "composite"),
        ("牛肉汤面", "beef noodle soup", "composite"),
        ("火锅", "hot pot", "composite"),
        ("麻辣香锅", "mala stir fry", "composite"),
        ("蛋炒饭", "egg fried rice", "composite"),
        ("组合沙拉", "mixed salad", "composite"),
    ],
}


def build(root: Path = Path(".")):
    foods = []
    for category, entries in GROUPS.items():
        for name, query, preparation in entries:
            foods.append(
                {
                    "food_id": f"F{len(foods) + 1:03d}",
                    "name_zh": name,
                    "name_en": query,
                    "primary_category": category,
                    "preparation": preparation,
                    "source_query": query,
                    "status": "candidate_identity_only",
                    "is_synthetic": "false",
                }
            )
    food_path = root / "data/curated/food_candidate_manifest.csv"
    if not food_path.exists():
        csv_write(food_path, foods, list(foods[0]))
    else:
        with food_path.open(newline="") as stream:
            if list(csv.DictReader(stream)) != foods:
                raise ValueError(
                    "existing candidate manifest differs; refusing to overwrite stable IDs"
                )
    rng = random.Random(23)
    menus = []
    for i in range(60):
        chosen = rng.sample(foods, 3)
        menus.append(
            {
                "menu_id": f"M{i + 1:03d}",
                "breakfast_candidate_id": chosen[0]["food_id"],
                "lunch_candidate_id": chosen[1]["food_id"],
                "dinner_candidate_id": chosen[2]["food_id"],
                "profile_id": ["balanced", "hedonist", "fitness", "long_termist"][
                    i % 4
                ],
                "construction_status": "awaiting_verified_foods_and_portions",
                "qa_class": "insufficient_data",
                "sampling_reason": "identity-only coverage draft; not a validated day plan",
                "seed": 23,
            }
        )
    menu_path = root / "data/menus/menu_candidate_manifest.csv"
    if not menu_path.exists():
        csv_write(menu_path, menus, list(menus[0]))
    for path, fields in [
        (root / "data/curated/foodbench48.csv", list(FoodVariant.model_fields)),
        (
            root / "data/reviews/food_review_ledger.csv",
            list(ReviewReceipt.model_fields),
        ),
        (root / "data/menus/day_menus.csv", ["menu_id", "day_plan_json"]),
    ]:
        if not path.exists():
            csv_write(path, [], fields)
    print(
        "Created identity-only drafts: 48 foods, 60 menus. Nutrition/approved food/menu rows: 0."
    )


if __name__ == "__main__":
    build()
