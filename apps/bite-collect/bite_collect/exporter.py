"""Separate training/calibration/test files; no consent or access secrets."""

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from .bank import CollectError, canonical
from .store import now

PAIR_FIELDS = [
    "user_id",
    "pair_id",
    "left_food_id",
    "right_food_id",
    "choice",
    "assignment_group",
    "query_policy",
    "split",
    "seen_left",
    "seen_right",
    "self_reported_hunger",
    "display_order_seed",
    "timestamp",
    "reaction_time_ms",
    "test_stratum",
    "bank_sha256",
    "assignment_sha256",
    "is_synthetic",
    "research_eligible",
]
RATING_FIELDS = [
    "user_id",
    "question_id",
    "food_id",
    "rating",
    "skip",
    "split",
    "timestamp",
    "reaction_time_ms",
    "bank_sha256",
    "assignment_sha256",
    "is_synthetic",
    "research_eligible",
]


def csv_bytes(rows, fields):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def export_bundle(store, purpose="synthetic"):
    if purpose != "synthetic":
        raise CollectError("禁止将 synthetic 数据导出为 HUMAN 研究数据")
    train, test, ratings = [], [], []
    banks, assignments = {}, {}
    # One SQLite read snapshot, even while another participant saves.
    with store.connect() as db:
        db.execute("BEGIN")
        for s in db.execute("SELECT * FROM sessions ORDER BY created_at"):
            bank, assigned = store.verify(db, s)
            banks[bank.sha256] = bank.document
            assignments[s["user_id"]] = {
                "bank_sha256": bank.sha256,
                "assignment_sha256": s["assignment_hash"],
                "questions": [json.loads(r["question_json"]) for r in assigned],
            }
            for row in db.execute(
                "SELECT a.question_json,r.* FROM assignments a JOIN responses r USING(user_id,question_id) WHERE user_id=? ORDER BY ordinal",
                (s["user_id"],),
            ):
                q, answer = (
                    json.loads(row["question_json"]),
                    json.loads(row["payload_json"]),
                )
                common = {
                    "user_id": s["user_id"],
                    "split": q["split"],
                    "timestamp": row["timestamp"],
                    "reaction_time_ms": row["reaction_time_ms"],
                    "bank_sha256": s["bank_hash"],
                    "assignment_sha256": s["assignment_hash"],
                    "is_synthetic": True,
                    "research_eligible": False,
                }
                if q["kind"] == "pair":
                    record = dict(
                        common,
                        **answer,
                        pair_id=q["question_id"],
                        left_food_id=q["left_food_id"],
                        right_food_id=q["right_food_id"],
                        assignment_group=s["assignment_group"],
                        query_policy=q["query_policy"],
                        display_order_seed=s["display_order_seed"],
                        test_stratum=q["test_stratum"],
                    )
                    (train if q["split"] == "train" else test).append(record)
                else:
                    ratings.append(
                        dict(
                            common,
                            **answer,
                            question_id=q["question_id"],
                            food_id=q["food_id"],
                        )
                    )
    files = {
        "synthetic/train_pairs.csv": csv_bytes(train, PAIR_FIELDS),
        "synthetic/test_pairs.csv": csv_bytes(test, PAIR_FIELDS),
        "synthetic/train_ratings.csv": csv_bytes(ratings, RATING_FIELDS),
        "synthetic/questionnaire_snapshots.json": canonical(banks).encode(),
        "synthetic/frozen_assignments.json": canonical(assignments).encode(),
    }
    manifest = {
        "schema_version": 1,
        "exported_at": now(),
        "provenance": "SYNTHETIC DEMO",
        "is_synthetic": True,
        "research_eligible": False,
        "real_participants": 0,
        "synthetic_sessions": len(assignments),
        "counts": {
            "train_pairs": len(train),
            "test_pairs": len(test),
            "train_ratings": len(ratings),
        },
        "null_encoding_csv": "empty cell means null; never zero",
        "reaction_time_definition": "server elapsed ms from first presentation to committed response; includes breaks/offline downtime; not active deliberation time",
        "training_input_allowlist": [
            "synthetic/train_pairs.csv",
            "synthetic/train_ratings.csv",
        ],
        "test_access": "evaluation only; never fit/select prompts/calibration/queries with test labels",
        "files": [
            {"path": name, "sha256": hashlib.sha256(content).hexdigest()}
            for name, content in files.items()
        ],
    }
    files["synthetic/manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return result.getvalue(), manifest


def write_export(store, target, purpose="synthetic"):
    target = Path(target).resolve()
    if "synthetic" not in target.parts:
        raise CollectError("导出必须置于 synthetic/ 目录")
    content, manifest = export_bundle(store, purpose)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output:
        output.write(content)
    return manifest
