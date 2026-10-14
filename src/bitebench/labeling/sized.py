"""Protocol-sized SYNTHETIC engineering fixtures and acceptance runner."""

import csv
import io
import json
import random
from collections import Counter
from pathlib import Path

from bitebench.core.hashing import content_hash
from bitebench.core.schemas import FoodVariant, TastePair
from bitebench.labeling.protocol import freeze_sized
from bitebench.labeling.questionnaire import (
    AnchorRating,
    MenuChoice,
    freeze_questionnaire,
)
from bitebench.labeling.storage import now
from bitebench.labeling.survey_storage import VISIBLE, SurveyStore


def immutable_write(path: Path, text: str) -> None:
    if path.exists():
        if path.read_text() != text:
            raise ValueError(
                "sized synthetic fixture already exists with different content"
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        stream.write(text)


def build(root: Path) -> tuple[Path, Path]:
    categories = [
        "staple",
        "meat_egg",
        "vegetable_legume",
        "fruit",
        "dessert",
        "beverage",
        "fast_food",
        "other",
    ]
    foods = []
    for n in range(48):
        foods.append(
            FoodVariant(
                food_id=f"synthetic_F{n + 1:03d}",
                name_zh=f"合成食物 {n + 1:02d}",
                primary_category=categories[n // 6],
                recipe_variant="protocol_sized_synthetic_v1",
                serving_g=100 + (n % 4) * 25,
                energy_kcal_per_100g=100 + n * 2,
                protein_g_per_100g=3 + n % 10,
                fat_g_per_100g=2 + n % 8,
                carbs_g_per_100g=15 + n % 20,
                fiber_g_per_100g=1 + n % 6,
                sodium_mg_per_100g=50 + n * 10,
                fruit_veg_g_per_serving=50 if n // 6 in {2, 3} else 0,
                source_system="synthetic_fixture",
                data_quality="unknown",
                is_synthetic=True,
            ).model_dump()
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(FoodVariant.model_fields), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(foods)
    food_path = root / "foods.csv"
    immutable_write(food_path, stream.getvalue())
    ids = [f["food_id"] for f in foods]
    menus = []
    for n in range(60):
        menus.append(
            dict(
                menu_id=f"synthetic_M{n + 1:03d}",
                profile_id="balanced",
                is_synthetic=True,
                meals=[
                    dict(
                        meal_id=f"synthetic_M{n + 1:03d}_{slot}",
                        slot=slot,
                        items=[dict(food_id=ids[i], servings=1 + (n // 48) * 0.5)],
                    )
                    for slot, i in zip(
                        ["breakfast", "lunch", "dinner"],
                        [n % 48, (n * 7 + 1) % 48, (n * 11 + 2) % 48],
                    )
                ],
            )
        )
    menu_path = root / "menus.json"
    immutable_write(menu_path, json.dumps(menus, ensure_ascii=False, indent=2) + "\n")
    return food_path, menu_path


def prepare(
    root: Path, split_path: Path, questionnaire_path: Path, seed: int = 23
) -> tuple[dict, dict]:
    foods, menus = build(root)
    protocol = freeze_sized(foods, split_path, seed)
    manifest = freeze_questionnaire(protocol, foods, menus, questionnaire_path)
    return protocol, manifest


def run(
    protocol: dict, manifest: dict, out: Path, seed: int = 17, sessions: int = 24
) -> dict:
    if not 1 <= sessions <= 24:
        raise ValueError("synthetic sessions must be 1..24")
    out.mkdir(parents=True, exist_ok=True)
    path = out / "synthetic" / "questionnaire.sqlite"
    if path.exists():
        raise ValueError("smoke output exists; use a fresh run directory")
    store = SurveyStore(path, protocol, manifest)
    summaries, groups = [], Counter()
    try:
        for session in range(sessions):
            user, _ = store.register_planned()
            store.acknowledge_demo(user)
            group = store.assignment_group(user)
            groups[group] += 1
            rng = random.Random(seed + session)
            utilities = {
                food_id: rng.uniform(-2, 2) for food_id in protocol["food_ids"]
            }
            while True:
                task = store.next_task(user)
                if task["kind"] == "complete":
                    break
                if task["kind"] == "taste":
                    pair = task["pair"]
                    display = store.taste_display(user, pair["pair_id"])
                    completed = store.summary(user)["taste_records"]
                    selected = (
                        "skip"
                        if completed % 17 == 16
                        else "tie"
                        if completed % 13 == 12
                        else (
                            "left"
                            if utilities[display["left_food_id"]]
                            > utilities[display["right_food_id"]]
                            else "right"
                        )
                    )
                    store.record(
                        TastePair(
                            user_id=user,
                            pair_id=pair["pair_id"],
                            **display,
                            choice=selected,
                            assignment_group=group,
                            query_policy=task["query_policy"],
                            split=pair["split"],
                            timestamp=now(),
                            is_synthetic=True,
                        )
                    )
                elif task["kind"] == "anchor":
                    value = 5 + 2 * utilities[task["food_id"]]
                    store.record_anchor(
                        AnchorRating(
                            user_id=user,
                            food_id=task["food_id"],
                            rating_0_10=value,
                            timestamp=now(),
                        )
                    )
                else:
                    pair = task["pair"]
                    display = store.menu_display(
                        user, pair["menu_pair_id"], task["stage"]
                    )
                    store.record_menu(
                        MenuChoice(
                            user_id=user,
                            menu_pair_id=pair["menu_pair_id"],
                            **display,
                            stage=task["stage"],
                            displayed_nutrition=task["stage"] == VISIBLE,
                            choice="right" if task["stage"] == VISIBLE else "left",
                            timestamp=now(),
                        )
                    )
            summary = store.summary(user)
            if summary != dict(
                is_synthetic=True,
                taste_records=50,
                anchor_records=8,
                menu_choice_records=24,
                independent_menu_pairs=12,
            ):
                raise ValueError("sized questionnaire counts failed")
            rows = store.training_answers(user)
            if len(rows) != 40 or len({r["pair_id"] for r in rows}) != 40:
                raise ValueError("training budget or uniqueness failed")
            traces = [
                json.loads(r[0])
                for r in store.db.execute(
                    "SELECT payload FROM queries WHERE user_id=?", (user,)
                )
            ]
            if Counter(t["query_policy"] for t in traces) != Counter(
                {"coverage_fixed": 20, group: 20}
            ):
                raise ValueError("coverage/adaptive budgets failed")
            tests = {p["pair_id"] for p in protocol["pairs"] if p["split"] == "test"}
            for trace in traces:
                if set(trace["candidate_pair_ids"]) & tests:
                    raise ValueError("test candidate leakage")
                if trace["model_state"]:
                    state = trace["model_state"]
                    if state["sha256"] != content_hash(
                        {k: v for k, v in state.items() if k != "sha256"}
                    ):
                        raise ValueError("query model state hash mismatch")
                    if set(state["food_ids"]) & set(protocol["heldout_food_ids"]):
                        raise ValueError("cold food in query model")
                    if state["training_records"] != trace["sequence"] - 1:
                        raise ValueError(
                            "query used future/unrelated training responses"
                        )
            summaries.append(summary | {"assignment_group": group})
        export_paths = dict(
            train=out / "synthetic" / "train.csv",
            test=out / "synthetic" / "test.csv",
            anchors=out / "synthetic" / "anchors.csv",
            menus=out / "synthetic" / "menus.csv",
        )
        exported = dict(
            train=store.export(export_paths["train"]),
            test=store.export(export_paths["test"], "test"),
            anchors=store.export_extra(export_paths["anchors"], "anchors"),
            menus=store.export_extra(export_paths["menus"], "menus"),
        )
        result = dict(
            status="PASS",
            scope="PROTOCOL_SIZED_SYNTHETIC_ENGINEERING_ONLY",
            is_synthetic=True,
            seed=seed,
            synthetic_sessions=sessions,
            real_participants=0,
            assignments=dict(groups),
            per_session=summaries,
            exported_rows=exported,
            unique_menu_pairs=12,
            participant_menu_comparisons=sessions * 12,
            split_sha256=protocol["sha256"],
            questionnaire_sha256=manifest["sha256"],
            model_version="synthetic_bt_query_v1",
            future_label_and_cold_food_audit="PASS",
            phase_2="BLOCKED",
            human_collection_enabled=False,
        )
        (out / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        store.close()
