import math

import pytest
from pydantic import ValidationError

from bitebench.core.schemas import AgentReport, DayPlan, FoodVariant
from bitebench.nutrition.calculator import calculate_day, portion


def food(**changes):
    base = dict(
        food_id="f1",
        name_zh="fixture",
        primary_category="staple",
        recipe_variant="fixture",
        serving_g=200,
        energy_kcal_per_100g=120,
        protein_g_per_100g=5,
        fiber_g_per_100g=3,
        sodium_mg_per_100g=100,
        fruit_veg_g_per_serving=0,
        source_system="synthetic_fixture",
        data_quality="unknown",
        is_synthetic=True,
    )
    return FoodVariant(**(base | changes))


def menu(food_id="f1", servings=1):
    return DayPlan(
        menu_id="d1",
        profile_id="balanced",
        is_synthetic=True,
        meals=[
            dict(
                meal_id="m1",
                slot="lunch",
                items=[dict(food_id=food_id, servings=servings)],
            )
        ],
    )


def test_units_and_portions():
    assert portion(food(), 1)["energy_kcal"] == 240
    assert portion(food(), 1.5)["sodium_mg"] == 300
    assert (
        calculate_day(menu(servings=1.5), {"f1": food()}, True)["totals"]["energy_kcal"]
        == 360
    )


def test_unknown_differs_from_zero():
    result = calculate_day(menu(), {"f1": food(fiber_g_per_100g=None)}, True)
    assert result["totals"]["fiber_g"] is None
    assert result["eligibility"] == "insufficient_data"
    assert (
        calculate_day(menu(), {"f1": food(fiber_g_per_100g=0)}, True)["eligibility"]
        == "eligible"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"serving_g": 0},
        {"serving_g": -1},
        {"serving_g": math.nan},
        {"protein_g_per_100g": -1},
        {"energy_kcal_per_100g": math.inf},
        {"fruit_veg_g_per_serving": 201},
        {"source_system": ""},
        {"data_quality": "database"},
    ],
)
def test_invalid_food(changes):
    with pytest.raises(ValidationError):
        food(**changes)


def test_unknown_id_and_synthetic_gate():
    with pytest.raises(ValueError, match="unknown food_id"):
        calculate_day(menu("absent"), {"f1": food()}, True)
    with pytest.raises(ValueError, match="synthetic"):
        calculate_day(menu(), {"f1": food()})


@pytest.mark.parametrize(
    "role,adjustment", [("T", 11), ("L", -11), ("N", 1), ("F", -1), ("T", math.nan)]
)
def test_invalid_adjustment(role, adjustment):
    with pytest.raises(ValidationError):
        AgentReport(
            role=role,
            adjustment=adjustment,
            evidence_ids=[],
            rationale="fixture",
            needs_review=False,
            issue_codes=[],
        )


def test_weights_and_nullable_total():
    from bitebench.nutrition.scoring import aggregate, validate_weights

    weights = dict(taste=0.35, nutrition=0.30, fitness=0.20, long_term=0.15)
    for value in [-1, math.nan, math.inf, 0.9]:
        with pytest.raises(ValueError):
            validate_weights(weights | {"taste": value})
    assert aggregate({}, weights, "insufficient_data")["total_0_100"] is None
    scores = dict(taste=50, nutrition=60, fitness=70, long_term=80)
    result = aggregate(scores, weights, "eligible")
    assert result["total_0_100"] == pytest.approx(61.5)
    assert {"q_t", "q_n", "q_f", "q_l"} <= result.keys()


@pytest.mark.parametrize("logit", [-1000, -3, 0, 3, 1000])
@pytest.mark.parametrize("choice", [False, True])
def test_pair_reversal_invariance(logit, choice):
    from bitebench.taste.metrics import binary_pair_nll

    assert binary_pair_nll(logit, choice) == pytest.approx(
        binary_pair_nll(-logit, not choice)
    )


def test_config_and_duplicate_food_gate(tmp_path):
    from pathlib import Path

    from bitebench.core.config import load_rubric
    from bitebench.core.validation import load_foods

    rubric = load_rubric(Path("config/rubric_v1.yaml"))
    assert len(rubric["profiles"]) == 4
    raw = Path("data/fixtures/synthetic/foods.csv").read_text()
    path = tmp_path / "duplicate.csv"
    path.write_text(raw + raw.splitlines()[1] + "\n")
    with pytest.raises(ValueError, match="duplicate food_id"):
        load_foods(path, True)
    with pytest.raises(ValueError, match="synthetic"):
        load_foods(Path("data/fixtures/synthetic/foods.csv"))
