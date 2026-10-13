"""Canonical input contracts; unknown nutrition remains None."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Category = Literal[
    "staple",
    "meat_egg",
    "vegetable_legume",
    "fruit",
    "dessert",
    "beverage",
    "fast_food",
    "other",
]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class FoodVariant(Contract):
    food_id: str = Field(min_length=1)
    name_zh: str = Field(min_length=1)
    name_en: str | None = None
    primary_category: Category
    recipe_variant: str = Field(min_length=1)
    serving_g: float = Field(gt=0)
    energy_kcal_per_100g: float | None = Field(default=None, ge=0)
    protein_g_per_100g: float | None = Field(default=None, ge=0)
    fat_g_per_100g: float | None = Field(default=None, ge=0)
    carbs_g_per_100g: float | None = Field(default=None, ge=0)
    fiber_g_per_100g: float | None = Field(default=None, ge=0)
    sodium_mg_per_100g: float | None = Field(default=None, ge=0)
    fruit_veg_g_per_serving: float | None = Field(default=None, ge=0)
    source_system: str = Field(min_length=1)
    source_record_id: str | None = None
    source_url: str | None = None
    retrieved_at: str | None = None
    data_quality: Literal["verified_label", "database", "recipe_estimate", "unknown"]
    image_path: str | None = None
    image_license: str | None = None
    is_synthetic: bool = False

    @model_validator(mode="after")
    def provenance(self):
        if (
            self.fruit_veg_g_per_serving is not None
            and self.fruit_veg_g_per_serving > self.serving_g
        ):
            raise ValueError("fruit/vegetable mass exceeds serving mass")
        if self.data_quality in {"database", "verified_label"} and not (
            self.source_record_id and self.source_url
        ):
            raise ValueError("database/label records require traceable ID and URL")
        if self.image_path and not self.image_license:
            raise ValueError("images require a license")
        return self


class MealItem(Contract):
    food_id: str
    servings: float = Field(gt=0)


class Meal(Contract):
    meal_id: str
    slot: Literal["breakfast", "lunch", "dinner", "snack"]
    items: list[MealItem] = Field(min_length=1)


class DayPlan(Contract):
    menu_id: str
    meals: list[Meal] = Field(min_length=1)
    profile_id: str
    history_ref: str | None = None
    is_synthetic: bool = False


class TastePair(Contract):
    user_id: str
    pair_id: str
    left_food_id: str
    right_food_id: str
    choice: Literal["left", "right", "tie", "skip"]
    assignment_group: str
    query_policy: str
    split: Literal["train", "val", "test"]
    seen_left: bool | None = None
    seen_right: bool | None = None
    self_reported_hunger: float | None = None
    display_order_seed: int
    timestamp: str
    is_synthetic: bool = False

    @model_validator(mode="after")
    def distinct_foods(self):
        if self.left_food_id == self.right_food_id:
            raise ValueError("comparison foods must differ")
        return self


class AgentReport(Contract):
    role: Literal["T", "N", "F", "L"]
    adjustment: float = Field(ge=-10, le=10)
    evidence_ids: list[str]
    rationale: str
    needs_review: bool
    issue_codes: list[str]

    @model_validator(mode="after")
    def fixed_oracle(self):
        if self.role in {"N", "F"} and self.adjustment != 0:
            raise ValueError("N/F cannot adjust numerical scores")
        return self
