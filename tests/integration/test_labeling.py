import json
from pathlib import Path

import pytest

from bitebench.core.schemas import TastePair
from bitebench.labeling.pair_selector import select_uncertain, training_pool
from bitebench.labeling.protocol import audit, freeze, read, verify_foods
from bitebench.labeling.storage import Store, now


@pytest.fixture
def protocol(tmp_path):
    return freeze(Path("data/fixtures/synthetic/foods.csv"), tmp_path / "split.json")


def test_frozen_partition_and_immutability(tmp_path, protocol):
    path = tmp_path / "split.json"
    assert freeze(Path("data/fixtures/synthetic/foods.csv"), path) == protocol
    with pytest.raises(ValueError, match="frozen"):
        freeze(Path("data/fixtures/synthetic/foods.csv"), path, seed=24)
    body = json.loads(path.read_text())
    body["seed"] = 999
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match="hash"):
        read(path)


def test_no_test_or_cold_food_in_active_pool(protocol):
    pool = training_pool(protocol)
    assert len(pool) == 4
    assert not any(
        set([p["left_food_id"], p["right_food_id"]]) & set(protocol["heldout_food_ids"])
        for p in pool
    )
    probabilities = {p["pair_id"]: 0.5 for p in pool}
    chosen = select_uncertain(protocol, probabilities)
    assert chosen["split"] == "train"
    with pytest.raises(ValueError, match="training candidates"):
        select_uncertain(protocol, probabilities | {"test_pair": 0.5})
    assert chosen not in training_pool(protocol, [chosen["pair_id"]])


def test_semantic_leakage_rejected_even_with_rehashed_protocol(protocol):
    from bitebench.core.hashing import content_hash

    broken = json.loads(json.dumps(protocol))
    broken["pairs"][0]["left_food_id"] = broken["heldout_food_ids"][0]
    broken["sha256"] = content_hash({k: v for k, v in broken.items() if k != "sha256"})
    with pytest.raises(ValueError, match="leakage"):
        audit(broken)


def test_snapshot_change_rejected(tmp_path, protocol):
    path = tmp_path / "foods.csv"
    path.write_text(
        Path("data/fixtures/synthetic/foods.csv").read_text().replace("120.0", "121.0")
    )
    with pytest.raises(ValueError, match="snapshot"):
        verify_foods(protocol, path)


def test_transactional_answers_reversal_resume_export_withdraw(tmp_path, protocol):
    path = tmp_path / "synthetic" / "labels.sqlite"
    store = Store(path, protocol)
    user, token = store.register()
    pair = training_pool(protocol)[0]
    display = store.display(user, pair["pair_id"], True, 23)
    assert display["left_food_id"] == pair["right_food_id"]
    answer = TastePair(
        user_id=user,
        pair_id=pair["pair_id"],
        **display,
        choice="left",
        assignment_group="random",
        query_policy="random",
        split="train",
        timestamp=now(),
        is_synthetic=True,
    )
    assert store.record(answer)
    assert not store.record(answer.model_copy(update={"timestamp": now()}))
    with pytest.raises(ValueError, match="conflict"):
        store.record(answer.model_copy(update={"choice": "right"}))
    with pytest.raises(ValueError, match="order"):
        store.display(user, pair["pair_id"], False, 23)
    with pytest.raises(ValueError, match="human"):
        store.record(answer.model_copy(update={"is_synthetic": False}))
    with pytest.raises(ValueError, match="split"):
        store.record(answer.model_copy(update={"split": "test"}))
    out = tmp_path / "export.csv"
    assert store.export(out) == 1
    assert "True" in out.read_text()
    assert token not in out.read_text()
    assert store.export(tmp_path / "test.csv", "test") == 0
    store.close()
    store = Store(path, protocol)
    assert not store.record(answer)
    assert not store.withdraw("invalid_token")
    assert store.withdraw(token)
    assert store.export(out) == 0
    assert store.db.execute("SELECT count(*) FROM displays").fetchone()[0] == 0
    store.close()


@pytest.mark.parametrize("choice", ["tie", "skip"])
def test_tie_and_skip_preserved(tmp_path, protocol, choice):
    store = Store(tmp_path / "synthetic" / "labels.sqlite", protocol)
    user, _ = store.register("active")
    pair = next(p for p in protocol["pairs"] if p["split"] == "test")
    display = store.display(user, pair["pair_id"], False, 1)
    store.record(
        TastePair(
            user_id=user,
            pair_id=pair["pair_id"],
            **display,
            choice=choice,
            assignment_group="active",
            query_policy="frozen_test",
            split="test",
            timestamp=now(),
            is_synthetic=True,
        )
    )
    assert store.export(tmp_path / "train.csv") == 0
    out = tmp_path / "test.csv"
    assert store.export(out, "test") == 1
    assert choice in out.read_text()
    store.close()


def test_storage_mode_path_and_protocol_binding(tmp_path, protocol):
    with pytest.raises(ValueError, match="human"):
        Store(tmp_path / "synthetic" / "labels.sqlite", protocol, "hybrid_pilot")
    with pytest.raises(ValueError, match="directory"):
        Store(tmp_path / "private" / "labels.sqlite", protocol)
    path = tmp_path / "synthetic" / "labels.sqlite"
    Store(path, protocol).close()
    other = freeze(
        Path("data/fixtures/synthetic/foods.csv"), tmp_path / "v2.json", seed=24
    )
    with pytest.raises(ValueError, match="different"):
        Store(path, other)


def test_unregistered_display_and_invalid_answer_do_not_write(tmp_path, protocol):
    import sqlite3

    from pydantic import ValidationError

    store = Store(tmp_path / "synthetic" / "labels.sqlite", protocol)
    pair = training_pool(protocol)[0]
    with pytest.raises(sqlite3.IntegrityError):
        store.display("unknown_user", pair["pair_id"], False, 23)
    user, _ = store.register()
    display = store.display(user, pair["pair_id"], False, 23)
    answer = TastePair(
        user_id=user,
        pair_id=pair["pair_id"],
        **display,
        choice="left",
        assignment_group="random",
        query_policy="random",
        split="train",
        timestamp=now(),
        is_synthetic=True,
    )
    with pytest.raises(ValidationError):
        store.record(answer.model_copy(update={"choice": "invented"}))
    with pytest.raises(ValueError, match="timezone"):
        store.record(answer.model_copy(update={"timestamp": "2026-10-13T10:00:00"}))
    assert store.db.execute("SELECT count(*) FROM answers").fetchone()[0] == 0
    store.close()
