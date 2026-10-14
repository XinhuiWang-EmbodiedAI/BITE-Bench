"""Versioned synthetic menu/anchor questionnaire, separate from formal protocol."""

import itertools
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from bitebench.core.hashing import content_hash
from bitebench.core.schemas import Contract, DayPlan
from bitebench.core.validation import load_foods
from bitebench.labeling.protocol import audit, verify_foods


class AnchorRating(Contract):
    user_id: str
    food_id: str
    rating_0_10: float = Field(ge=0, le=10)
    timestamp: datetime
    is_synthetic: Literal[True] = True

    @model_validator(mode="after")
    def aware(self):
        require_aware(self.timestamp)
        return self


class MenuChoice(Contract):
    user_id: str
    menu_pair_id: str
    menu_a_id: str
    menu_b_id: str
    stage: Literal["taste_hidden_nutrition", "overall_visible_nutrition"]
    choice: Literal["left", "right", "tie", "skip"]
    displayed_nutrition: bool
    order_randomization: int
    timestamp: datetime
    is_synthetic: Literal[True] = True

    @model_validator(mode="after")
    def valid(self):
        require_aware(self.timestamp)
        if self.menu_a_id == self.menu_b_id:
            raise ValueError("menu choices must differ")
        if self.displayed_nutrition != (self.stage == "overall_visible_nutrition"):
            raise ValueError("nutrition visibility differs from stage")
        return self


def require_aware(timestamp: datetime) -> None:
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must include timezone")


def audit_questionnaire(manifest: dict, protocol: dict) -> None:
    audit(protocol)
    if content_hash(
        {k: v for k, v in manifest.items() if k != "sha256"}
    ) != manifest.get("sha256"):
        raise ValueError("questionnaire hash mismatch")
    if (
        manifest.get("is_synthetic") is not True
        or manifest.get("mode") != "synthetic_only"
    ):
        raise ValueError("human collection disabled")
    if manifest["split_sha256"] != protocol["sha256"]:
        raise ValueError("questionnaire split mismatch")
    menus = [DayPlan.model_validate(m) for m in manifest["menus"]]
    ids = [m.menu_id for m in menus]
    if len(set(ids)) != len(ids) or len(ids) < 2:
        raise ValueError("invalid menu IDs")
    for menu in menus:
        if not menu.is_synthetic or not {"breakfast", "lunch", "dinner"} <= {
            m.slot for m in menu.meals
        }:
            raise ValueError("requires synthetic full-day menus")
        if not {i.food_id for m in menu.meals for i in m.items} <= set(
            protocol["food_ids"]
        ):
            raise ValueError("unknown menu food")
    seen_ids, seen_pairs = set(), set()
    for p in manifest["menu_pairs"]:
        pair = tuple(sorted([p["menu_a_id"], p["menu_b_id"]]))
        if len(set(pair)) != 2 or not set(pair) <= set(ids):
            raise ValueError("invalid menu pair")
        if p["menu_pair_id"] in seen_ids or pair in seen_pairs:
            raise ValueError("duplicate menu pair")
        if p["split"] != "test":
            raise ValueError("synthetic questionnaire menu pairs must be test")
        seen_ids.add(p["menu_pair_id"])
        seen_pairs.add(pair)
    if not seen_pairs:
        raise ValueError("menu pairs required")

    if manifest.get("version") == "synthetic_sized_questionnaire_v1":
        final = set(manifest["final_eval_menu_ids"])
        dev = set(manifest["development_menu_ids"])
        if (
            len(ids) != 60
            or len(final) != 24
            or len(dev) != 36
            or final & dev
            or final | dev != set(ids)
        ):
            raise ValueError("invalid sized menu partition")
        if (
            len(manifest["menu_pairs"]) != 12
            or set(
                f
                for p in manifest["menu_pairs"]
                for f in [p["menu_a_id"], p["menu_b_id"]]
            )
            != final
        ):
            raise ValueError("requires 12 frozen final menu pairs")


def freeze_questionnaire(
    protocol: dict, food_path: Path, menu_path: Path, out: Path
) -> dict:
    verify_foods(protocol, food_path)
    foods = load_foods(food_path, True)
    if not all(f.is_synthetic for f in foods.values()):
        raise ValueError("synthetic foods required")
    menus = [
        DayPlan.model_validate(m).model_dump()
        for m in json.loads(menu_path.read_text())
    ]
    ids = sorted(m["menu_id"] for m in menus)
    body = dict(
        version="synthetic_questionnaire_v1",
        mode="synthetic_only",
        is_synthetic=True,
        scope="partial_engineering_fixture_not_formal_protocol",
        split_sha256=protocol["sha256"],
        menus=menus,
        menu_pairs=[
            dict(
                menu_pair_id=f"synthetic_menu_{a}_{b}",
                menu_a_id=a,
                menu_b_id=b,
                split="test",
            )
            for a, b in itertools.combinations(ids, 2)
        ],
    )
    if protocol.get("version") == "synthetic_sized_split_v1":
        if len(ids) != 60:
            raise ValueError("sized questionnaire requires 60 synthetic menus")
        body.update(
            version="synthetic_sized_questionnaire_v1",
            scope="protocol_sized_engineering_fixture_not_formal_protocol",
            final_eval_menu_ids=ids[:24],
            development_menu_ids=ids[24:],
            menu_pairs=[
                dict(
                    menu_pair_id=f"sized_menu_{a}_{b}",
                    menu_a_id=a,
                    menu_b_id=b,
                    split="test",
                )
                for a, b in zip(ids[:24:2], ids[1:24:2])
            ],
        )
    manifest = body | {"sha256": content_hash(body)}
    audit_questionnaire(manifest, protocol)
    if out.exists():
        existing = read_questionnaire(out, protocol)
        if existing != manifest:
            raise ValueError("frozen questionnaire exists; use a new versioned path")
        return existing
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return manifest


def read_questionnaire(path: Path, protocol: dict) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    audit_questionnaire(manifest, protocol)
    return manifest
