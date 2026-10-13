"""Review receipts are supplied by humans; this module never creates approval."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from bitebench.core.hashing import content_hash
from bitebench.core.schemas import Contract, FoodVariant
from bitebench.nutrition.calculator import REQUIRED


class ReviewReceipt(Contract):
    food_id: str
    food_data_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_status: Literal[
        "unreviewed", "auto_checked", "needs_review", "approved", "rejected"
    ]
    risk_level: Literal["low", "medium", "high"]
    reviewer_id: str | None = None
    reviewed_at: datetime | None = None
    evidence_ref: str | None = None
    decision_note: str | None = None
    actor_type: Literal["human", "automation"] = "automation"
    is_synthetic: bool = False

    @model_validator(mode="after")
    def accountable_approval(self):
        if self.review_status == "approved":
            if (
                self.actor_type != "human"
                or not self.reviewer_id
                or not self.reviewer_id.strip()
            ):
                raise ValueError("approval requires an identified human reviewer")
            if (
                not self.reviewed_at
                or not self.reviewed_at.tzinfo
                or self.reviewed_at.utcoffset() is None
            ):
                raise ValueError("approval requires a timezone-aware timestamp")
            if (
                not self.evidence_ref
                or not self.evidence_ref.strip()
                or not self.decision_note
                or not self.decision_note.strip()
            ):
                raise ValueError("approval requires evidence and a decision note")
        return self


def food_hash(food: FoodVariant) -> str:
    return content_hash(food.model_dump())


def review_state(
    food: FoodVariant, receipt: ReviewReceipt | None, formal: bool = True
) -> dict:
    if formal and (food.is_synthetic or (receipt and receipt.is_synthetic)):
        return {"review_status": "needs_review", "reason_code": "SYNTHETIC_NOT_ALLOWED"}
    if receipt is None:
        return {"review_status": "unreviewed", "reason_code": "NO_REVIEW_RECEIPT"}
    if receipt.food_id != food.food_id or receipt.food_data_sha256 != food_hash(food):
        return {
            "review_status": "needs_review",
            "reason_code": "APPROVAL_HASH_INVALIDATED",
        }
    if (
        receipt.review_status == "approved"
        and receipt.evidence_ref != f"{food.source_system}:{food.source_record_id}"
    ):
        return {
            "review_status": "needs_review",
            "reason_code": "REVIEW_EVIDENCE_MISMATCH",
        }
    return {"review_status": receipt.review_status, "reason_code": None}


def read_ledger(path: Path) -> dict[str, ReviewReceipt]:
    if not path.is_file():
        return {}
    records = {}
    with path.open(newline="") as stream:
        for row in csv.DictReader(stream):
            row = {key: None if value == "" else value for key, value in row.items()}
            receipt = ReviewReceipt.model_validate(row)
            if receipt.food_id in records:
                raise ValueError("ambiguous duplicate food review receipts")
            records[receipt.food_id] = receipt
    return records


def formal_eligibility(food: FoodVariant, receipt: ReviewReceipt | None) -> dict:
    state = review_state(food, receipt)
    missing = [
        name
        for name in REQUIRED
        if getattr(
            food,
            "fruit_veg_g_per_serving" if name == "fruit_veg_g" else name + "_per_100g",
        )
        is None
    ]
    problems = []
    if (
        food.data_quality == "unknown"
        or not food.source_record_id
        or not food.source_url
        or not food.retrieved_at
    ):
        problems.append("MISSING_SOURCE_PROVENANCE")
    if food.retrieved_at:
        try:
            timestamp = datetime.fromisoformat(food.retrieved_at)
            if not timestamp.tzinfo or timestamp.utcoffset() is None:
                problems.append("INVALID_SOURCE_TIMESTAMP")
        except ValueError:
            problems.append("INVALID_SOURCE_TIMESTAMP")
    if food.energy_kcal_per_100g == 0 and food.primary_category != "beverage":
        problems.append("ZERO_ENERGY_NON_BEVERAGE")
    if state["review_status"] != "approved":
        problems.append(state["reason_code"] or "NOT_HUMAN_APPROVED")
    return state | {
        "eligibility": "insufficient_data" if missing or problems else "eligible",
        "unknown_fields": missing,
        "reason_codes": problems,
    }
