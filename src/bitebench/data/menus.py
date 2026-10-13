"""Reviewed menu validation; identity-only drafts cannot be scored."""

import csv
import json
from pathlib import Path

from bitebench.core.config import load_rubric
from bitebench.core.schemas import DayPlan, FoodVariant
from bitebench.data.reviews import formal_eligibility, read_ledger
from bitebench.nutrition.calculator import calculate_day


def menu_report(
    menu_path: Path,
    food_path: Path,
    ledger_path: Path,
    rubric_path: Path = Path("config/rubric_v1.yaml"),
) -> dict:
    foods = {}
    source_errors = []
    with food_path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            try:
                food = FoodVariant.model_validate(
                    {
                        key: None if value in {"", "null", "None"} else value
                        for key, value in row.items()
                    }
                )
                if food.food_id in foods:
                    raise ValueError("duplicate food_id")
                foods[food.food_id] = food
            except ValueError as error:
                source_errors.append(str(error))
    ledger = read_ledger(ledger_path)
    rubric = load_rubric(rubric_path)
    if menu_path.suffix == ".json":
        raw_menus = json.loads(menu_path.read_text())
    else:
        with menu_path.open(newline="") as stream:
            raw_menus = list(csv.DictReader(stream))
    records, seen = [], set()
    for raw in raw_menus:
        identifier = raw.get("menu_id")
        try:
            if "day_plan_json" in raw:
                menu = DayPlan.model_validate_json(raw["day_plan_json"])
                if identifier != menu.menu_id:
                    raise ValueError("CSV and payload menu IDs differ")
            else:
                menu = DayPlan.model_validate(raw)
            if menu.menu_id in seen:
                raise ValueError("duplicate menu ID")
            seen.add(menu.menu_id)
            if menu.profile_id not in rubric["profiles"]:
                raise ValueError("unknown profile")
            calculation = calculate_day(menu, foods)
            food_ids = {item.food_id for meal in menu.meals for item in meal.items}
            invalid_foods = [
                food_id
                for food_id in food_ids
                if formal_eligibility(foods[food_id], ledger.get(food_id))[
                    "eligibility"
                ]
                != "eligible"
            ]
            full_day = {"breakfast", "lunch", "dinner"} <= {
                meal.slot for meal in menu.meals
            }
            eligible = (
                calculation["eligibility"] == "eligible"
                and not invalid_foods
                and full_day
            )
            energy = calculation["totals"]["energy_kcal"]
            target = rubric["reference_goals"]["energy_target_kcal"]
            tolerance = rubric["reference_goals"]["energy_tolerance_fraction"]
            qa = (
                "insufficient_data"
                if not eligible
                else (
                    "reference_valid"
                    if abs(energy - target) <= target * tolerance
                    else "stress_case"
                )
            )
            records.append(
                {
                    "menu_id": menu.menu_id,
                    "eligibility": "eligible" if eligible else "insufficient_data",
                    "qa_class": qa,
                    "unreviewed_or_incomplete_food_ids": sorted(invalid_foods),
                    "full_day": full_day,
                    "totals": calculation["totals"],
                    "unknown_fields": calculation["unknown_fields"],
                }
            )
        except (ValueError, TypeError) as error:
            records.append(
                {
                    "menu_id": identifier,
                    "eligibility": "insufficient_data",
                    "qa_class": "insufficient_data",
                    "error": str(error),
                }
            )
    eligible = sum(row["eligibility"] == "eligible" for row in records)
    return {
        "status": "PASS"
        if records and not source_errors and eligible == len(records)
        else "BLOCKED",
        "menu_rows": len(records),
        "eligible_rows": eligible,
        "target_menu_rows": 60,
        "records": records,
        "food_schema_errors": source_errors,
    }
