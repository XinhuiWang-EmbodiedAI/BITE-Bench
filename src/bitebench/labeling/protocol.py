"""Immutable synthetic-only partitions, created before any responses."""

import itertools
import json
import random
from pathlib import Path

from bitebench.core.hashing import content_hash
from bitebench.core.validation import load_foods


def audit(protocol: dict) -> None:
    body = {k: v for k, v in protocol.items() if k != "sha256"}
    if content_hash(body) != protocol.get("sha256"):
        raise ValueError("split hash mismatch")
    if (
        protocol.get("mode") != "synthetic_only"
        or protocol.get("is_synthetic") is not True
    ):
        raise ValueError("human collection disabled")
    foods = set(protocol["food_ids"])
    cold = set(protocol["heldout_food_ids"])
    anchors = set(protocol["anchor_food_ids"])
    if not cold or not cold < foods or not anchors <= foods - cold:
        raise ValueError("invalid cold-food or anchor partition")
    seen, pairs = set(), set()
    for item in protocol["pairs"]:
        pair = tuple(sorted([item["left_food_id"], item["right_food_id"]]))
        if len(set(pair)) != 2 or not set(pair) <= foods:
            raise ValueError("invalid comparison foods")
        if item["pair_id"] in seen or pair in pairs:
            raise ValueError("duplicate pair")
        seen.add(item["pair_id"])
        pairs.add(pair)
        if item["split"] not in {"train", "test"}:
            raise ValueError("invalid split")
        if item["split"] == "train" and set(pair) & cold:
            raise ValueError("cold-food training leakage")
        if item["split"] == "test" and item["stratum"] != (
            "cold_food" if set(pair) & cold else "known_food"
        ):
            raise ValueError("invalid test stratum")

    if protocol.get("version") == "synthetic_sized_split_v1":
        coverage = [p for p in protocol["pairs"] if p.get("query_phase") == "coverage"]
        candidates = [p for p in protocol["pairs"] if p.get("query_phase") == "query"]
        tests = [p for p in protocol["pairs"] if p["split"] == "test"]
        if len(foods) != 48 or len(cold) != 8 or len(anchors) != 8:
            raise ValueError("sized fixture requires 48 foods, 8 heldout, 8 anchors")
        if len(coverage) != 20 or len(candidates) < 20 or len(tests) != 10:
            raise ValueError("invalid sized query budgets")
        if (
            protocol.get("training_budget") != 40
            or protocol.get("adaptive_budget") != 20
        ):
            raise ValueError("invalid sized training budget")
        if any(p["split"] != "train" for p in coverage + candidates):
            raise ValueError("coverage/query phases must be training")
        if any(
            p.get("query_phase") not in {"coverage", "query", "test"}
            for p in protocol["pairs"]
        ):
            raise ValueError("invalid query phase")
        if any(p.get("query_phase") != "test" for p in tests):
            raise ValueError("invalid test phase")
        if sum(p["stratum"] == "cold_food" for p in tests) != 5:
            raise ValueError("requires 5 known and 5 cold test pairs")
        if {
            f for p in coverage for f in [p["left_food_id"], p["right_food_id"]]
        } != foods - cold:
            raise ValueError("coverage must touch all training foods")
        if (
            protocol.get("assignment_order", []).count("active") != 12
            or protocol.get("assignment_order", []).count("random") != 12
        ):
            raise ValueError("requires balanced 24-session assignment plan")


def freeze(food_path: Path, out: Path, seed: int = 23) -> dict:
    foods = load_foods(food_path, allow_synthetic=True)
    if len(foods) < 4 or not all(f.is_synthetic for f in foods.values()):
        raise ValueError("requires at least four synthetic foods")
    ids = sorted(foods)
    rng = random.Random(seed)
    cold = [ids[-1]]
    known_pairs = list(itertools.combinations(ids[:-1], 2))
    rng.shuffle(known_pairs)
    test_known = known_pairs[:2]
    train = known_pairs[2:]
    test_cold = [(item, cold[0]) for item in ids[:-1]][:2]
    pairs = []
    for split, stratum, pool in [
        ("train", "known_food", train),
        ("test", "known_food", test_known),
        ("test", "cold_food", test_cold),
    ]:
        for left, right in pool:
            pairs.append(
                dict(
                    pair_id=f"synthetic_{split}_{left}_{right}",
                    left_food_id=left,
                    right_food_id=right,
                    split=split,
                    stratum=stratum,
                )
            )
    body = dict(
        version="synthetic_split_v1",
        mode="synthetic_only",
        is_synthetic=True,
        scope="partial_engineering_fixture_not_formal_protocol",
        seed=seed,
        food_ids=ids,
        heldout_food_ids=cold,
        anchor_food_ids=ids[:-1],
        pairs=pairs,
        dataset_sha256=content_hash([foods[k].model_dump() for k in ids]),
    )
    protocol = body | {"sha256": content_hash(body)}
    audit(protocol)
    if out.exists():
        existing = read(out)
        if existing != protocol:
            raise ValueError("frozen split exists; use a new versioned path")
        return existing
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return protocol


def read(path: Path) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    audit(protocol)
    return protocol


def verify_foods(protocol: dict, food_path: Path) -> None:
    audit(protocol)
    foods = load_foods(food_path, allow_synthetic=True)
    digest = content_hash([foods[k].model_dump() for k in sorted(foods)])
    if digest != protocol["dataset_sha256"]:
        raise ValueError("food snapshot differs from frozen split")


def freeze_sized(food_path: Path, out: Path, seed: int = 23) -> dict:
    foods = load_foods(food_path, True)
    if len(foods) != 48 or not all(f.is_synthetic for f in foods.values()):
        raise ValueError("sized freeze requires 48 explicitly synthetic foods")
    ids = sorted(foods)
    known, cold = ids[:-8], ids[-8:]
    rng = random.Random(seed)
    coverage_pairs = list(zip(known[::2], known[1::2]))
    remaining = [p for p in itertools.combinations(known, 2) if p not in coverage_pairs]
    rng.shuffle(remaining)
    known_tests, candidate_pairs = remaining[:5], remaining[5:]
    cold_tests = list(zip(known[:5], cold[:5]))
    pairs = []
    for phase, stratum, pool in [
        ("coverage", "known_food", coverage_pairs),
        ("query", "known_food", candidate_pairs),
        ("test", "known_food", known_tests),
        ("test", "cold_food", cold_tests),
    ]:
        for left, right in pool:
            pairs.append(
                dict(
                    pair_id=f"sized_{phase}_{left}_{right}",
                    left_food_id=left,
                    right_food_id=right,
                    split="test" if phase == "test" else "train",
                    stratum=stratum,
                    query_phase=phase,
                )
            )
    groups = ["active"] * 12 + ["random"] * 12
    rng.shuffle(groups)
    body = dict(
        version="synthetic_sized_split_v1",
        mode="synthetic_only",
        is_synthetic=True,
        scope="protocol_sized_engineering_fixture_not_formal_protocol",
        seed=seed,
        food_ids=ids,
        heldout_food_ids=cold,
        anchor_food_ids=known[:8],
        pairs=pairs,
        training_budget=40,
        adaptive_budget=20,
        assignment_order=groups,
        dataset_sha256=content_hash([foods[k].model_dump() for k in ids]),
    )
    protocol = body | {"sha256": content_hash(body)}
    audit(protocol)
    if out.exists():
        existing = read(out)
        if existing != protocol:
            raise ValueError("frozen split exists; use a new versioned path")
        return existing
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return protocol
