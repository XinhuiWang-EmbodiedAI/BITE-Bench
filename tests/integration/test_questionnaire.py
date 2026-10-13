import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from bitebench.cli import app
from bitebench.core.schemas import TastePair
from bitebench.labeling.protocol import freeze
from bitebench.labeling.questionnaire import (
    AnchorRating,
    MenuChoice,
    audit_questionnaire,
    freeze_questionnaire,
)
from bitebench.labeling.storage import now
from bitebench.labeling.survey_storage import HIDDEN, VISIBLE, SurveyStore


@pytest.fixture
def survey(tmp_path):
    foods = Path("data/fixtures/synthetic/foods.csv")
    split_path = tmp_path / "split.json"
    protocol = freeze(foods, split_path)
    manifest_path = tmp_path / "questionnaire.json"
    manifest = freeze_questionnaire(
        protocol,
        foods,
        Path("data/fixtures/synthetic/questionnaire_menus.json"),
        manifest_path,
    )
    return protocol, manifest, split_path, manifest_path


def test_questionnaire_immutable_and_full_day_checks(tmp_path, survey):
    protocol, manifest, _, target = survey
    foods = Path("data/fixtures/synthetic/foods.csv")
    menus = Path("data/fixtures/synthetic/questionnaire_menus.json")
    assert freeze_questionnaire(protocol, foods, menus, target) == manifest
    changed = json.loads(menus.read_text())
    changed[0]["meals"][0]["items"][0]["servings"] = 3
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="frozen questionnaire"):
        freeze_questionnaire(protocol, foods, path, target)
    with pytest.raises(ValueError, match="full-day"):
        freeze_questionnaire(
            protocol,
            foods,
            Path("data/fixtures/synthetic/menus.json"),
            tmp_path / "invalid.json",
        )
    broken = json.loads(json.dumps(manifest))
    broken["menus"][0]["is_synthetic"] = False
    from bitebench.core.hashing import content_hash

    broken["sha256"] = content_hash({k: v for k, v in broken.items() if k != "sha256"})
    with pytest.raises(ValueError, match="synthetic full-day"):
        audit_questionnaire(broken, protocol)


def test_anchor_range_leakage_resume_and_withdraw(tmp_path, survey):
    protocol, manifest, _, _ = survey
    store = SurveyStore(tmp_path / "synthetic" / "survey.sqlite", protocol, manifest)
    user, token = store.register()
    assert store.resume(token) == user
    with pytest.raises(ValueError, match="token"):
        store.resume("invalid")
    with pytest.raises(ValidationError):
        AnchorRating(user_id=user, food_id="f", rating_0_10=11, timestamp=now())
    with pytest.raises(ValidationError):
        AnchorRating(
            user_id=user, food_id="f", rating_0_10=float("nan"), timestamp=now()
        )
    with pytest.raises(ValidationError):
        AnchorRating(
            user_id=user,
            food_id="f",
            rating_0_10=5,
            timestamp=now(),
            is_synthetic=False,
        )
    with pytest.raises(ValueError, match="training anchors"):
        store.record_anchor(
            AnchorRating(
                user_id=user,
                food_id=protocol["heldout_food_ids"][0],
                rating_0_10=5,
                timestamp=now(),
            )
        )
    answer = AnchorRating(
        user_id=user,
        food_id=protocol["anchor_food_ids"][0],
        rating_0_10=7,
        timestamp=now(),
    )
    assert store.record_anchor(answer)
    assert not store.record_anchor(answer)
    with pytest.raises(ValueError, match="conflict"):
        store.record_anchor(answer.model_copy(update={"rating_0_10": 8}))
    assert store.export_extra(tmp_path / "anchors.csv", "anchors") == 1
    assert store.withdraw(token)
    assert store.export_extra(tmp_path / "anchors.csv", "anchors") == 0
    with pytest.raises(ValueError, match="token"):
        store.resume(token)
    store.close()


def test_menu_order_visibility_counts_and_conflict(tmp_path, survey):
    protocol, manifest, _, _ = survey
    path = tmp_path / "synthetic" / "survey.sqlite"
    store = SurveyStore(path, protocol, manifest)
    user, token = store.register()
    pair_id = manifest["menu_pairs"][0]["menu_pair_id"]
    with pytest.raises(ValueError, match="hidden"):
        store.menu_display(user, pair_id, VISIBLE)
    display = store.menu_display(user, pair_id, HIDDEN)
    hidden = MenuChoice(
        user_id=user,
        menu_pair_id=pair_id,
        **display,
        stage=HIDDEN,
        choice="left",
        displayed_nutrition=False,
        timestamp=now(),
    )
    with pytest.raises(ValidationError):
        MenuChoice(**(hidden.model_dump() | {"displayed_nutrition": True}))
    visible = MenuChoice(
        **(hidden.model_dump() | {"stage": VISIBLE, "displayed_nutrition": True})
    )
    with pytest.raises(ValueError, match="hidden"):
        store.record_menu(visible)
    assert store.record_menu(hidden)
    assert store.menu_display(user, pair_id, VISIBLE) == display
    assert store.record_menu(visible)
    assert not store.record_menu(visible)
    with pytest.raises(ValueError, match="conflict"):
        store.record_menu(visible.model_copy(update={"choice": "right"}))
    with pytest.raises(ValueError, match="display mismatch"):
        store.record_menu(visible.model_copy(update={"menu_a_id": "unknown"}))
    assert store.summary(user)["menu_choice_records"] == 2
    assert store.summary(user)["independent_menu_pairs"] == 1
    assert store.export_extra(tmp_path / "menus.csv", "menus") == 2
    store.close()
    store = SurveyStore(path, protocol, manifest)
    assert store.resume(token) == user
    assert store.menu_display(user, pair_id, VISIBLE) == display
    assert store.withdraw(token)
    for table in ["menu_answers", "menu_displays", "anchors"]:
        assert store.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    store.close()


def test_all_hidden_before_any_visible(tmp_path, survey):
    from bitebench.core.hashing import content_hash

    protocol, manifest, _, _ = survey
    modified = json.loads(json.dumps(manifest))
    extra = json.loads(json.dumps(modified["menus"][0]))
    extra["menu_id"] = "synthetic_extra"
    modified["menus"].append(extra)
    first = modified["menu_pairs"][0]
    modified["menu_pairs"].append(
        dict(
            menu_pair_id="synthetic_extra_pair",
            menu_a_id=first["menu_a_id"],
            menu_b_id="synthetic_extra",
            split="test",
        )
    )
    modified["sha256"] = content_hash(
        {k: v for k, v in modified.items() if k != "sha256"}
    )
    store = SurveyStore(tmp_path / "synthetic" / "survey.sqlite", protocol, modified)
    user, _ = store.register()
    display = store.menu_display(user, first["menu_pair_id"], HIDDEN)
    store.record_menu(
        MenuChoice(
            user_id=user,
            menu_pair_id=first["menu_pair_id"],
            **display,
            stage=HIDDEN,
            choice="skip",
            displayed_nutrition=False,
            timestamp=now(),
        )
    )
    with pytest.raises(ValueError, match="all hidden"):
        store.menu_display(user, first["menu_pair_id"], VISIBLE)
    store.close()


def test_concurrent_duplicate_submission(tmp_path, survey):
    protocol, manifest, _, _ = survey
    path = tmp_path / "synthetic" / "survey.sqlite"
    store = SurveyStore(path, protocol, manifest)
    user, _ = store.register()
    task = store.next_task(user)
    pair = task["pair"]
    display = store.taste_display(user, pair["pair_id"])
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
    store.close()

    def write(_):
        writer = SurveyStore(path, protocol, manifest)
        try:
            return writer.record(answer)
        finally:
            writer.close()

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sorted(workers.map(write, [1, 2])) == [False, True]


def test_terminal_complete_pause_resume_and_hidden_nutrition(tmp_path, survey):
    protocol, manifest, split_path, manifest_path = survey
    database = tmp_path / "synthetic" / "cli.sqlite"
    args = [
        "label",
        "app",
        "--protocol",
        str(split_path),
        "--questionnaire",
        str(manifest_path),
        "--database",
        str(database),
    ]
    runner = CliRunner()
    result = runner.invoke(app, args, input="DEMO\nnew\nexit\n")
    assert result.exit_code == 0, result.output
    assert "已保存" in result.output
    assert "energy_kcal" not in result.output
    store = SurveyStore(database, protocol, manifest)
    user = store.db.execute("SELECT user_id FROM users").fetchone()[0]
    assert store.summary(user)["taste_records"] == 0
    store.close()
    token = (
        result.output.split("恢复/撤回 token（请自行保存）：")[1]
        .splitlines()[0]
        .strip()
    )
    answers = "".join("left\nunknown\nunknown\nunknown\n" for _ in protocol["pairs"])
    inputs = (
        "DEMO\nresume\n"
        + token
        + "\n"
        + answers
        + "7\n" * len(protocol["anchor_food_ids"])
        + "left\n" * 2
    )
    result = runner.invoke(app, args, input=inputs)
    assert result.exit_code == 0, result.output
    assert "合成演示完成" in result.output
    assert "energy_kcal" in result.output
    hidden = result.output.split("菜单阶段：隐藏营养")[1].split(
        "菜单阶段：显示合成营养"
    )[0]
    assert "energy_kcal" not in hidden
    store = SurveyStore(database, protocol, manifest)
    assert store.summary(user) == dict(
        is_synthetic=True,
        taste_records=8,
        anchor_records=4,
        menu_choice_records=2,
        independent_menu_pairs=1,
    )
    assert store.next_task(user)["kind"] == "complete"
    store.close()
    result = runner.invoke(app, args, input="DEMO\nwithdraw\n" + token + "\n")
    assert result.exit_code == 0
    assert "记录已撤回" in result.output


def test_unacknowledged_demo_and_human_mode_do_not_create_database(tmp_path, survey):
    _, _, split, manifest = survey
    database = tmp_path / "synthetic" / "cli.sqlite"
    args = [
        "label",
        "app",
        "--protocol",
        str(split),
        "--questionnaire",
        str(manifest),
        "--database",
        str(database),
    ]
    runner = CliRunner()
    result = runner.invoke(app, args, input="NO\n")
    assert result.exit_code == 0
    assert not database.exists()
    result = runner.invoke(app, args + ["--mode", "hybrid_pilot"])
    assert result.exit_code == 2
    assert not database.exists()


def test_random_query_audit_excludes_test_and_active_is_explicitly_unavailable(
    tmp_path, survey
):
    protocol, manifest, _, _ = survey
    store = SurveyStore(tmp_path / "synthetic" / "survey.sqlite", protocol, manifest)
    user, token = store.register()
    store.acknowledge_demo(user)
    task = store.next_task(user)
    assert store.next_task(user) == task
    rows = store.db.execute(
        "SELECT payload FROM queries WHERE user_id=?", (user,)
    ).fetchall()
    assert len(rows) == 1
    trace = json.loads(rows[0][0])
    test_ids = {p["pair_id"] for p in protocol["pairs"] if p["split"] == "test"}
    assert not set(trace["candidate_pair_ids"]) & test_ids
    assert trace["model_state_sha256"] is None
    assert trace["query_policy"] == "random"
    active_user, _ = store.register("active")
    active_task = store.next_task(active_user)
    assert active_task["query_policy"] == "active"
    active_trace = json.loads(
        store.db.execute(
            "SELECT payload FROM queries WHERE user_id=?", (active_user,)
        ).fetchone()[0]
    )
    assert active_trace["model_state_sha256"]
    assert active_trace["model_state"]["fitted_binary_records"] == 0
    assert store.withdraw(token)
    assert (
        store.db.execute(
            "SELECT count(*) FROM queries WHERE user_id=?", (user,)
        ).fetchone()[0]
        == 0
    )
    assert (
        store.db.execute(
            "SELECT count(*) FROM notices WHERE user_id=?", (user,)
        ).fetchone()[0]
        == 0
    )
    store.close()
