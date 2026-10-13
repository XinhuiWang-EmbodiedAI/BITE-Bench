import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bitebench.cli import app
from bitebench.core.hashing import content_hash
from bitebench.core.schemas import TastePair
from bitebench.labeling.protocol import audit, freeze
from bitebench.labeling.query_model import QueryModel
from bitebench.labeling.questionnaire import freeze_questionnaire
from bitebench.labeling.sized import prepare, run
from bitebench.labeling.storage import now
from bitebench.labeling.survey_storage import SurveyStore


@pytest.fixture
def small(tmp_path):
    foods = Path("data/fixtures/synthetic/foods.csv")
    protocol = freeze(foods, tmp_path / "split.json")
    manifest = freeze_questionnaire(
        protocol,
        foods,
        Path("data/fixtures/synthetic/questionnaire_menus.json"),
        tmp_path / "questionnaire.json",
    )
    return protocol, manifest


def row(pair, **updates):
    return (
        dict(
            user_id="synthetic_u",
            pair_id=pair["pair_id"],
            left_food_id=pair["left_food_id"],
            right_food_id=pair["right_food_id"],
            choice="left",
            assignment_group="active",
            query_policy="active",
            split=pair["split"],
            display_order_seed=23,
            timestamp=now(),
            is_synthetic=True,
        )
        | updates
    )


def test_query_model_direction_tie_skip_and_training_only(small):
    protocol, _ = small
    pairs = [p for p in protocol["pairs"] if p["split"] == "train"]
    rows = [row(p) for p in pairs]
    model = QueryModel()
    state = model.fit(protocol, rows)
    pair = pairs[0]
    assert model.probability(pair["left_food_id"], pair["right_food_id"]) > 0.5
    reversed_rows = [
        r
        | dict(
            left_food_id=r["right_food_id"],
            right_food_id=r["left_food_id"],
            choice="right",
        )
        for r in rows
    ]
    other = QueryModel()
    assert other.fit(protocol, reversed_rows)["sha256"] == state["sha256"]
    assert other.probability(
        pair["right_food_id"], pair["left_food_id"]
    ) == pytest.approx(
        1 - model.probability(pair["left_food_id"], pair["right_food_id"])
    )
    ties = [row(p, choice="tie" if i % 2 else "skip") for i, p in enumerate(pairs)]
    empty = QueryModel()
    empty_state = empty.fit(protocol, ties)
    assert empty_state["fitted_binary_records"] == 0
    assert empty_state["excluded_tie_skip"] == len(ties)
    assert empty.probability(pair["left_food_id"], pair["right_food_id"]) == 0.5
    test = next(p for p in protocol["pairs"] if p["split"] == "test")
    with pytest.raises(ValueError, match="training records only"):
        QueryModel().fit(protocol, [row(test)])
    with pytest.raises(ValueError, match="training records only"):
        QueryModel().fit(protocol, [row(pair, is_synthetic=False)])
    with pytest.raises(ValueError, match="duplicate"):
        QueryModel().fit(protocol, [rows[0], rows[0]])
    with pytest.raises(ValueError, match="one synthetic session"):
        QueryModel().fit(protocol, [rows[0], rows[1] | {"user_id": "other"}])
    with pytest.raises(ValueError, match="heldout"):
        model.probability(protocol["heldout_food_ids"][0], pair["right_food_id"])


def test_active_snapshots_resume_and_test_answers_do_not_fit(tmp_path, small):
    protocol, manifest = small
    path = tmp_path / "synthetic" / "survey.sqlite"
    store = SurveyStore(path, protocol, manifest)
    user, token = store.register("active")
    task = store.next_task(user)
    assert task["query_policy"] == "active"
    assert store.next_task(user) == task
    display = store.taste_display(user, task["pair"]["pair_id"])
    store.record(TastePair(**row(task["pair"], user_id=user, **display)))
    before = QueryModel().fit(protocol, store.training_answers(user))
    test = next(p for p in protocol["pairs"] if p["split"] == "test")
    display = store.taste_display(user, test["pair_id"])
    store.record(
        TastePair(**row(test, user_id=user, query_policy="frozen_test", **display))
    )
    after = QueryModel().fit(protocol, store.training_answers(user))
    assert after == before
    next_task = store.next_task(user)
    trace = json.loads(
        store.db.execute(
            "SELECT payload FROM queries WHERE user_id=? AND pair_id=?",
            (user, next_task["pair"]["pair_id"]),
        ).fetchone()[0]
    )
    assert trace["model_state"]["training_records"] == 1
    assert trace["model_state_sha256"] == before["sha256"]
    candidates = {
        p["pair_id"]: p
        for p in protocol["pairs"]
        if p["split"] == "train" and p["pair_id"] != task["pair"]["pair_id"]
    }
    predictor = QueryModel()
    predictor.fit(protocol, store.training_answers(user))
    scores = {
        k: predictor.probability(v["left_food_id"], v["right_food_id"])
        for k, v in candidates.items()
    }
    expected = min(scores, key=lambda k: (-scores[k] * (1 - scores[k]), k))
    assert next_task["pair"]["pair_id"] == expected
    store.close()
    store = SurveyStore(path, protocol, manifest)
    assert store.resume(token) == user
    assert store.next_task(user) == next_task
    store.close()


@pytest.fixture
def sized(tmp_path):
    return prepare(
        tmp_path / "fixtures", tmp_path / "split.json", tmp_path / "questionnaire.json"
    )


def test_sized_partitions_and_immutable_existing_files(tmp_path, sized):
    protocol, manifest = sized
    assert len(protocol["food_ids"]) == 48
    assert len(protocol["heldout_food_ids"]) == 8
    assert len(protocol["anchor_food_ids"]) == 8
    tests = [p for p in protocol["pairs"] if p["split"] == "test"]
    assert len(tests) == 10
    assert sum(p["stratum"] == "cold_food" for p in tests) == 5
    assert len(manifest["menus"]) == 60 and len(manifest["menu_pairs"]) == 12
    assert not set(manifest["development_menu_ids"]) & set(
        manifest["final_eval_menu_ids"]
    )
    assert (
        prepare(
            tmp_path / "fixtures",
            tmp_path / "split.json",
            tmp_path / "questionnaire.json",
        )
        == sized
    )
    with pytest.raises(ValueError, match="frozen split"):
        prepare(
            tmp_path / "fixtures",
            tmp_path / "split.json",
            tmp_path / "questionnaire.json",
            seed=99,
        )
    broken = json.loads(json.dumps(protocol))
    broken["training_budget"] = 41
    broken["sha256"] = content_hash({k: v for k, v in broken.items() if k != "sha256"})
    with pytest.raises(ValueError, match="budget"):
        audit(broken)


def test_sized_prevents_unissued_answers_and_early_tests(tmp_path, sized):
    protocol, manifest = sized
    store = SurveyStore(tmp_path / "synthetic" / "survey.sqlite", protocol, manifest)
    user, _ = store.register_planned()
    group = store.assignment_group(user)
    pool = next(p for p in protocol["pairs"] if p.get("query_phase") == "query")
    display = store.taste_display(user, pool["pair_id"])
    with pytest.raises(ValueError, match="issued"):
        store.record(
            TastePair(
                **row(
                    pool,
                    user_id=user,
                    assignment_group=group,
                    query_policy=group,
                    **display,
                )
            )
        )
    test = next(p for p in protocol["pairs"] if p["split"] == "test")
    display = store.taste_display(user, test["pair_id"])
    with pytest.raises(ValueError, match="40 training"):
        store.record(
            TastePair(
                **row(
                    test,
                    user_id=user,
                    assignment_group=group,
                    query_policy="frozen_test",
                    **display,
                )
            )
        )
    task = store.next_task(user)
    assert task["query_policy"] == "coverage_fixed"
    store.close()


def test_sized_assignment_plan_balanced_and_not_reused_after_withdrawal(
    tmp_path, sized
):
    protocol, manifest = sized
    store = SurveyStore(tmp_path / "synthetic" / "survey.sqlite", protocol, manifest)
    observed = []
    for _ in range(24):
        user, token = store.register_planned()
        observed.append(store.assignment_group(user))
        store.withdraw(token)
    assert observed == protocol["assignment_order"]
    assert observed.count("active") == observed.count("random") == 12
    with pytest.raises(ValueError, match="exhausted"):
        store.register_planned()
    store.close()


def test_sized_two_session_end_to_end_and_no_overwrite(tmp_path, sized):
    protocol, manifest = sized
    out = tmp_path / "run"
    result = run(protocol, manifest, out, sessions=2)
    assert result["exported_rows"] == dict(train=80, test=20, anchors=16, menus=48)
    assert result["real_participants"] == 0
    assert result["participant_menu_comparisons"] == 24
    with pytest.raises(ValueError, match="fresh run"):
        run(protocol, manifest, out, sessions=2)


def test_cli_active_group_reaches_query_without_human_mode(tmp_path, small):
    _, _ = small
    result = CliRunner().invoke(
        app,
        [
            "label",
            "app",
            "--group",
            "active",
            "--protocol",
            str(tmp_path / "split.json"),
            "--questionnaire",
            str(tmp_path / "questionnaire.json"),
            "--database",
            str(tmp_path / "synthetic" / "cli.sqlite"),
        ],
        input="DEMO\nnew\nexit\n",
    )
    assert result.exit_code == 0, result.output
    assert "已保存" in result.output
