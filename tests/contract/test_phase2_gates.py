"""Contract checks use synthetic data and isolated temporary directories."""

import json
from pathlib import Path

import httpx
from typer.testing import CliRunner

from bitebench.cli import app
from bitebench.data.curation import data_report, prepare, rank_matches
from bitebench.data.usda_client import USDAClient


def test_missing_key_prepares_actionable_queue_without_approval(tmp_path):
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "food_id,name_zh,name_en,primary_category,preparation,source_query,is_synthetic\nfixture_id,合成夹具,fixture,staple,cooked,fixture,true\n"
    )
    with USDAClient(
        None, tmp_path / "raw", transport=httpx.MockTransport(lambda r: None)
    ) as client:
        report = prepare(manifest, tmp_path / "reviews", client)
    assert (
        report["candidate_rows"] == 1
        and report["network_requests"] == 0
        and report["approved_rows"] == 0
    )
    action = json.loads(
        (tmp_path / "reviews/human_action_queue.jsonl").read_text().splitlines()[0]
    )
    assert action["reason_code"] == "NO_API_KEY"
    assert action["evidence_paths"] == []
    assert action["status"] == "PENDING_HUMAN"


def test_identity_matching_rejects_raw_cooked_confusion():
    candidate = {"source_query": "broccoli raw", "preparation": "raw"}
    matches = rank_matches(
        candidate,
        [
            {"fdcId": 1, "description": "Broccoli cooked"},
            {"fdcId": 2, "description": "Broccoli raw"},
        ],
    )
    assert matches[0]["fdc_id"] == 2
    assert matches[1]["identity_flags"] == ["RAW_COOKED_MISMATCH"]


def test_empty_formal_data_and_missing_reviews_are_blocked(tmp_path):
    path = tmp_path / "food.csv"
    path.write_text("food_id,name_zh\n")
    report = data_report(path, tmp_path / "ledger.csv")
    assert (
        report["food_rows"] == 0
        and report["approved_rows"] == 0
        and report["status"] == "BLOCKED"
    )
    result = CliRunner().invoke(
        app,
        [
            "data",
            "validate",
            "--input",
            str(path),
            "--strict",
            "--ledger",
            str(tmp_path / "ledger.csv"),
        ],
    )
    assert result.exit_code == 2 and json.loads(result.stdout)["status"] == "BLOCKED"


def test_formal_report_rejects_synthetic_even_if_nutrients_complete(tmp_path):
    path = Path("data/fixtures/synthetic/foods.csv")
    report = data_report(path, tmp_path / "ledger.csv")
    assert (
        report["food_rows"] == 5
        and report["synthetic_rows"] == 5
        and report["eligible_rows"] == 0
    )
    assert report["status"] == "BLOCKED"


def test_review_ui_disables_incomplete_approval_and_escapes_source_text(tmp_path):
    from bitebench.core.schemas import FoodVariant
    from bitebench.data.review_ui import render_review_cards

    food = {field: None for field in FoodVariant.model_fields}
    food.update(
        food_id="fixture_id",
        name_zh="<script>malicious</script>",
        source_system="synthetic_fixture",
        data_quality="unknown",
        is_synthetic=True,
    )
    cards = tmp_path / "cards.json"
    cards.write_text(
        json.dumps(
            [
                {
                    "proposed_food": food,
                    "missing_fields": ["serving_g"],
                    "risk_level": "high",
                }
            ]
        )
    )
    out = tmp_path / "review.html"
    render_review_cards(cards, out)
    text = out.read_text()
    assert 'data-decision="approved" disabled' in text
    assert "<script>malicious</script>" not in text
    assert "尚无决定" in text
