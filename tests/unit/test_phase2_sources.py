"""All fabricated responses here are explicitly synthetic test fixtures."""

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from bitebench.core.schemas import FoodVariant
from bitebench.data.normalization import normalize_fdc
from bitebench.data.recipe_builder import estimate_recipe
from bitebench.data.reviews import (
    ReviewReceipt,
    food_hash,
    formal_eligibility,
    review_state,
)
from bitebench.data.usda_client import SourceError, USDAClient
from bitebench.nutrition.units import convert, per_serving_to_100g, salt_to_sodium_mg


def snapshot(rows, **extra):
    return {
        "retrieved_at": "2026-10-13T00:00:00+00:00",
        "response": {
            "fdcId": 999,
            "dataType": "Foundation",
            "is_synthetic": True,
            "foodNutrients": rows,
            **extra,
        },
    }


def nutrient(identifier, value, unit):
    return {"nutrient": {"id": identifier, "unitName": unit}, "amount": value}


def toy_food(**changes):
    return FoodVariant(
        **(
            dict(
                food_id="fixture_f",
                name_zh="合成夹具",
                primary_category="staple",
                recipe_variant="synthetic_v1",
                serving_g=200,
                energy_kcal_per_100g=120,
                protein_g_per_100g=5,
                fiber_g_per_100g=3,
                sodium_mg_per_100g=100,
                fruit_veg_g_per_serving=0,
                source_system="synthetic_fixture",
                data_quality="unknown",
                is_synthetic=True,
            )
            | changes
        )
    )


def receipt(food, **changes):
    return ReviewReceipt(
        **(
            dict(
                food_id=food.food_id,
                food_data_sha256=food_hash(food),
                review_status="approved",
                risk_level="low",
                reviewer_id="synthetic_reviewer",
                reviewed_at=datetime.now(timezone.utc),
                evidence_ref=f"{food.source_system}:{food.source_record_id}",
                decision_note="SYNTHETIC REVIEW TEST ONLY",
                actor_type="human",
                is_synthetic=True,
            )
            | changes
        )
    )


def test_units_unknown_and_distinct_salt():
    assert convert(418.4, "kJ", "kcal") == pytest.approx(100)
    assert convert(0.1, "g", "mg") == 100
    assert salt_to_sodium_mg(1) == 400
    assert salt_to_sodium_mg(None) is None
    assert per_serving_to_100g(240, 200) == 120
    assert per_serving_to_100g(None, 200) is None
    with pytest.raises(ValueError):
        convert(1, "salt_g", "mg")
    with pytest.raises(ValueError):
        per_serving_to_100g(1, 0)


def test_fdc_mapping_kj_missing_and_original_units():
    result = normalize_fdc(
        snapshot(
            [
                nutrient(1062, 418.4, "kJ"),
                nutrient(1093, 0.1, "g"),
                nutrient(1003, 5000, "mg"),
            ]
        )
    )
    assert result["is_synthetic"] is True
    assert result["nutrients"]["energy_kcal_per_100g"] == pytest.approx(100)
    assert result["nutrients"]["sodium_mg_per_100g"] == 100
    assert result["nutrients"]["protein_g_per_100g"] == 5
    assert result["nutrients"]["fiber_g_per_100g"] is None
    assert result["audit"][0]["source_unit"] == "kJ"


def test_identity_and_energy_basis_are_not_names_only():
    result = normalize_fdc(
        snapshot([nutrient(2048, 95, "kcal"), nutrient(2047, 100, "kcal")])
    )
    assert result["energy_nutrient_id"] == 2047
    assert "MULTIPLE_ENERGY_BASES_REVIEW" in result["issues"]
    result = normalize_fdc(
        snapshot([nutrient(1008, 418.4, "kJ"), nutrient(7777, 100, "kcal")])
    )
    assert result["nutrients"]["energy_kcal_per_100g"] is None


def test_conflict_stays_unknown_even_with_later_duplicate():
    result = normalize_fdc(
        snapshot(
            [
                nutrient(1093, 10, "mg"),
                nutrient(1093, 20, "mg"),
                nutrient(1093, 10, "mg"),
            ]
        )
    )
    assert result["nutrients"]["sodium_mg_per_100g"] is None
    assert "CONFLICTING_VALUES:1093" in result["issues"]


def test_ml_and_loq_are_not_assumed_grams_and_zero():
    result = normalize_fdc(
        snapshot([nutrient(1093, 10, "mg")], dataType="Branded", servingSizeUnit="ml")
    )
    assert result["nutrients"]["sodium_mg_per_100g"] is None
    result = normalize_fdc(snapshot([nutrient(1093, 0, "mg") | {"loq": 0.03}]))
    assert result["nutrients"]["sodium_mg_per_100g"] is None
    assert "BELOW_LOQ:1093" in result["issues"]


def test_no_key_makes_no_request_and_no_fake_cache(tmp_path):
    calls = []
    with USDAClient(
        None, tmp_path, transport=httpx.MockTransport(lambda r: calls.append(r))
    ) as client:
        with pytest.raises(SourceError, match="NO_API_KEY"):
            client.search("fixture")
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_redacted_cache_is_replayable_and_tamper_detected(tmp_path):
    secret = "synthetic-secret"
    body = {
        "foods": [],
        "api_key": secret,
        "note": f"echo={secret}",
        "is_synthetic": True,
    }
    with USDAClient(
        secret,
        tmp_path,
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)),
    ) as client:
        first = client.search("fixture")
        second = client.search("fixture")
        assert first["cache_hit"] is False and second["cache_hit"] is True
        assert client.requests_sent == 1
        assert secret not in "".join(p.read_text() for p in tmp_path.glob("*.json"))
        Path(first["snapshot_path"]).write_text('{"tampered": true}')
        with pytest.raises(SourceError, match="CACHE_HASH_MISMATCH"):
            client.search("fixture")


def test_429_retry_budget_and_long_deadline(tmp_path):
    waits = []
    responses = iter(
        [
            httpx.Response(429, headers={"Retry-After": "2"}),
            httpx.Response(200, json={"foods": [], "is_synthetic": True}),
        ]
    )
    with USDAClient(
        "fixture",
        tmp_path,
        transport=httpx.MockTransport(lambda r: next(responses)),
        sleep=waits.append,
    ) as client:
        client.search("fixture")
        assert client.requests_sent == 2 and waits == [2]
    with USDAClient(
        "fixture",
        tmp_path / "other",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(429, headers={"Retry-After": "120"})
        ),
        sleep=waits.append,
    ) as client:
        with pytest.raises(SourceError, match="RATE_LIMITED"):
            client.search("fixture")
        assert client.requests_sent == 1 and waits == [2]


def test_errors_cannot_echo_credentials(tmp_path):
    with USDAClient(
        "synthetic-secret",
        tmp_path,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(403, json={"error": str(r.url)})
        ),
    ) as client:
        with pytest.raises(SourceError) as caught:
            client.search("fixture")
    assert str(caught.value) == "HTTP_ERROR"
    assert "synthetic-secret" not in str(caught.value)


def test_auto_checked_and_changed_hash_never_approve():
    food = toy_food()
    approved = receipt(food)
    assert review_state(food, approved, formal=False)["review_status"] == "approved"
    assert (
        review_state(food, receipt(food, review_status="auto_checked"), formal=False)[
            "review_status"
        ]
        == "auto_checked"
    )
    modified = food.model_copy(update={"serving_g": 201})
    assert (
        review_state(modified, approved, formal=False)["reason_code"]
        == "APPROVAL_HASH_INVALIDATED"
    )
    assert formal_eligibility(food, approved)["eligibility"] != "eligible"


@pytest.mark.parametrize(
    "changes",
    [
        {"reviewer_id": ""},
        {"reviewer_id": " "},
        {"actor_type": "automation"},
        {"reviewed_at": datetime(2026, 10, 13)},
        {"evidence_ref": ""},
        {"decision_note": ""},
    ],
)
def test_approval_without_accountable_receipt_rejected(changes):
    with pytest.raises(ValidationError):
        receipt(toy_food(), **changes)


def test_recipe_finished_yield_unknown_propagation_and_quality():
    result = estimate_recipe(
        [(toy_food(), 100)],
        80,
        "synthetic fixture: all retained oil/salt included in ingredient masses",
    )
    assert result["nutrients"]["energy_kcal_per_100g"] == 150
    assert result["data_quality"] == "recipe_estimate" and result["is_synthetic"]
    assert result["fruit_veg_g_per_serving"] is None
    result = estimate_recipe([(toy_food(fiber_g_per_100g=None), 100)], 80, "fixture")
    assert result["nutrients"]["fiber_g_per_100g"] is None
    with pytest.raises(ValueError):
        estimate_recipe([(toy_food(), 100)], 0, "fixture")


def test_search_uses_official_post_body_and_cache_can_replay_without_key(tmp_path):
    def respond(request):
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["query"] == "synthetic fixture"
        assert body["dataType"] == ["Foundation", "SR Legacy", "Survey (FNDDS)"]
        assert "api_key" not in body
        return httpx.Response(200, json={"foods": [], "is_synthetic": True})

    with USDAClient(
        "fixture", tmp_path, transport=httpx.MockTransport(respond)
    ) as client:
        client.search("synthetic fixture")
    with USDAClient(
        None, tmp_path, transport=httpx.MockTransport(lambda r: None)
    ) as client:
        assert client.search("synthetic fixture")["cache_hit"]
        assert client.requests_sent == 0


def test_network_budget_includes_retry_attempts(tmp_path):
    with USDAClient(
        "fixture",
        tmp_path,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(429, headers={"Retry-After": "0"})
        ),
        sleep=lambda seconds: None,
    ) as client:
        client.network_budget = 1
        with pytest.raises(SourceError, match="NETWORK_BUDGET_EXHAUSTED"):
            client.search("fixture")
        assert client.requests_sent == 1


def test_extreme_density_is_flagged_not_rewritten():
    result = normalize_fdc(
        snapshot(
            [
                nutrient(1008, 1000, "kcal"),
                nutrient(1003, 1, "g"),
                nutrient(1004, 1, "g"),
                nutrient(1005, 1, "g"),
            ]
        )
    )
    assert result["nutrients"]["energy_kcal_per_100g"] == 1000
    assert "EXTREME_ENERGY_DENSITY_REVIEW" in result["issues"]
    assert "MACRO_ENERGY_CHECK_REVIEW" in result["issues"]
