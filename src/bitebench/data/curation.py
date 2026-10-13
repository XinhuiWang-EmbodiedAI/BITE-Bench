"""Candidate preparation and actionable queues; no automatic human approval."""

import csv
import json
import re
from pathlib import Path

from bitebench.core.schemas import FoodVariant
from bitebench.data.normalization import normalize_fdc
from bitebench.data.reviews import formal_eligibility, read_ledger
from bitebench.data.usda_client import SourceError, USDAClient


def csv_write(path: Path, rows: list[dict], fields: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def rank_matches(candidate: dict, matches: list[dict]) -> list[dict]:
    query_words = set(re.findall(r"[a-z]+", candidate["source_query"].lower()))
    ranked = []
    for match in matches:
        words = set(re.findall(r"[a-z]+", match.get("description", "").lower()))
        flags = []
        if candidate["preparation"] == "raw" and words & {
            "cooked",
            "fried",
            "boiled",
            "roasted",
        }:
            flags.append("RAW_COOKED_MISMATCH")
        if candidate["preparation"] == "cooked" and "raw" in words:
            flags.append("RAW_COOKED_MISMATCH")
        score = len(words & query_words) / max(1, len(query_words)) - len(flags)
        ranked.append(
            {
                "fdc_id": match["fdcId"],
                "description": match.get("description"),
                "match_score": score,
                "identity_flags": flags,
            }
        )
    return sorted(ranked, key=lambda item: (-item["match_score"], item["fdc_id"]))


def prepare(
    manifest: Path,
    out: Path,
    client: USDAClient,
    network_budget: int = 0,
    only_food_ids: set[str] | None = None,
) -> dict:
    with manifest.open(newline="") as stream:
        candidates = list(csv.DictReader(stream))
    if len({row["food_id"] for row in candidates}) != len(candidates):
        raise ValueError("duplicate candidate food IDs")
    out.mkdir(parents=True, exist_ok=True)
    proposed, cards, actions = [], [], []
    start_requests = client.requests_sent
    client.network_budget = start_requests + network_budget
    for candidate in candidates:
        food = {field: None for field in FoodVariant.model_fields}
        food.update(
            {
                key: candidate[key]
                for key in ("food_id", "name_zh", "name_en", "primary_category")
            }
        )
        food.update(
            recipe_variant=candidate["preparation"],
            source_system="unresolved",
            data_quality="unknown",
            is_synthetic=str(candidate.get("is_synthetic", "false")).lower() == "true",
        )
        reason = "SOURCE_LOOKUP_PENDING"
        evidence, ranked, nutrition_audit, issues = [], [], [], []
        source_details = None
        http_status = None
        if only_food_ids is None or candidate["food_id"] in only_food_ids:
            try:
                search = client.search(candidate["source_query"], 5)
                evidence.append(search["snapshot_path"])
                ranked = rank_matches(candidate, search["response"].get("foods", []))
                viable = [item for item in ranked if not item["identity_flags"]]
                if not viable:
                    reason = "NO_IDENTITY_MATCH"
                else:
                    snapshot = client.fetch(viable[0]["fdc_id"])
                    evidence.append(snapshot["snapshot_path"])
                    normalized = normalize_fdc(snapshot)
                    food.update(normalized["nutrients"])
                    food.update(
                        source_system="USDA_FDC",
                        source_record_id=normalized["source_record_id"],
                        source_url=normalized["source_url"],
                        retrieved_at=normalized["retrieved_at"],
                        data_quality="database",
                        is_synthetic=food["is_synthetic"] or normalized["is_synthetic"],
                    )
                    source_details = {
                        "description": snapshot["response"].get("description"),
                        "data_type": snapshot["response"].get("dataType"),
                        "publication_date": snapshot["response"].get("publicationDate"),
                        "brand_owner": snapshot["response"].get("brandOwner"),
                        "food_portions": snapshot["response"].get("foodPortions", []),
                        "energy_nutrient_id": normalized.get("energy_nutrient_id"),
                    }
                    nutrition_audit = normalized["audit"]
                    issues = normalized["issues"]
                    reason = "IDENTITY_PORTION_AND_NUTRITION_REVIEW_REQUIRED"
            except SourceError as error:
                reason = error.reason_code
                http_status = error.status_code
        risk = "high" if candidate["preparation"] == "composite" else "medium"
        missing = [
            field
            for field in (
                "serving_g",
                "energy_kcal_per_100g",
                "protein_g_per_100g",
                "fiber_g_per_100g",
                "sodium_mg_per_100g",
                "fruit_veg_g_per_serving",
            )
            if food[field] is None
        ]
        proposed.append(food)
        action_id = "REVIEW-" + candidate["food_id"]
        cards.append(
            {
                "action_id": action_id,
                "candidate": candidate,
                "proposed_food": food,
                "review_status": "needs_review",
                "risk_level": risk,
                "risk_flags": [reason, *issues],
                "selected_source": source_details,
                "http_status": http_status,
                "ranked_matches": ranked,
                "unit_audit": nutrition_audit,
                "missing_fields": missing,
                "evidence_paths": evidence,
                "source_license": "CC0"
                if food["source_system"] == "USDA_FDC"
                else None,
                "recommendation": "Confirm exact identity, edible serving and nutrient coverage; no approval recorded.",
            }
        )
        actions.append(
            {
                "action_id": action_id,
                "kind": "food_source_match",
                "object_ref": candidate["food_id"],
                "risk": risk,
                "status": "PENDING_HUMAN",
                "reason_code": reason,
                "ready_for_review": bool(evidence),
                "question": (
                    f"核对 {candidate['name_zh']} 的来源与可食份量/配方；当前缺失：{', '.join(missing)}"
                    if evidence
                    else f"{candidate['name_zh']} 等待自动来源检索；暂不要求手填营养数值。"
                ),
                "options": [
                    "approve_after_complete_evidence",
                    "request_revision",
                    "exclude",
                ],
                "evidence_paths": evidence,
                "default_safe_action": "exclude_from_formal_analysis",
                "blocks": ["Phase2 formal subset", "Phase8 formal scoring"],
            }
        )
    if any(item["reason_code"] == "NO_API_KEY" for item in actions):
        actions.append(
            {
                "action_id": "SETUP-USDA-KEY",
                "kind": "api_configuration",
                "object_ref": "USDA_FDC",
                "risk": "medium",
                "status": "PENDING_HUMAN",
                "reason_code": "NO_API_KEY",
                "ready_for_review": True,
                "question": "在本地 .env 设置个人 USDA_FDC_API_KEY；不要发到聊天或提交 Git。系统会自动检索，不需手填食品营养。",
                "options": ["configure_local_key", "continue_offline"],
                "evidence_paths": [],
                "default_safe_action": "continue_independent_engineering",
                "blocks": ["Phase2 source acquisition"],
            }
        )
    csv_write(
        out / "proposed_food_records.csv", proposed, list(FoodVariant.model_fields)
    )
    (out / "review_cards.json").write_text(
        json.dumps(cards, ensure_ascii=False, indent=2) + "\n"
    )
    (out / "human_action_queue.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in actions)
    )
    csv_write(
        out / "food_review_queue.csv",
        [
            {
                key: item[key]
                for key in [
                    "action_id",
                    "object_ref",
                    "risk",
                    "status",
                    "reason_code",
                    "question",
                ]
            }
            for item in actions
            if item["kind"] == "food_source_match"
        ],
        ["action_id", "object_ref", "risk", "status", "reason_code", "question"],
    )
    return {
        "status": "PASS",
        "scope": "queue_preparation_only",
        "candidate_rows": len(candidates),
        "proposed_rows": len(proposed),
        "approved_rows": 0,
        "pending_actions": len(actions),
        "actionable_actions": sum(item["ready_for_review"] for item in actions),
        "source_backed_proposals": sum(
            row["source_system"] == "USDA_FDC" for row in proposed
        ),
        "network_requests": client.requests_sent - start_requests,
    }


def write_human_queue(queue: Path, out: Path, only_actionable: bool = True):
    actions = [
        json.loads(line) for line in queue.read_text().splitlines() if line.strip()
    ]
    text = "# Human Actions\n\n这些是待审核建议，不是已批准食品或真人回答。\n\n"
    text += f"共 {len(actions)} 项待办；仅展示可立即处理的项目。其余缺少来源的食品由系统等待自动检索。\n\n"
    text += "| ID | 风险 | 对象 | 原因 | 最小人工任务 |\n|---|---|---|---|---|\n"
    for item in sorted(
        actions, key=lambda row: (row["risk"] != "high", row["action_id"])
    ):
        if item["status"] == "PENDING_HUMAN" and (
            not only_actionable or item.get("ready_for_review", False)
        ):
            text += f"| {item['action_id']} | {item['risk']} | {item['object_ref']} | {item['reason_code']} | {item['question'].replace('|', '/')} |\n"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)


def data_report(path: Path, ledger: Path) -> dict:
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    receipts = read_ledger(ledger)
    quality = {
        key: 0 for key in ("verified_label", "database", "recipe_estimate", "unknown")
    }
    records, errors = [], []
    seen = set()
    for i, row in enumerate(rows, 2):
        try:
            food = FoodVariant.model_validate(
                {
                    key: None if value in {"", "null", "None"} else value
                    for key, value in row.items()
                }
            )
            if food.food_id in seen:
                raise ValueError("duplicate food_id")
            seen.add(food.food_id)
            quality[food.data_quality] += 1
            records.append(
                {
                    "food_id": food.food_id,
                    "is_synthetic": food.is_synthetic,
                    **formal_eligibility(food, receipts.get(food.food_id)),
                }
            )
        except ValueError as error:
            errors.append({"csv_line": i, "error": str(error)})
    eligible = sum(row["eligibility"] == "eligible" for row in records)
    return {
        "status": "PASS"
        if rows and not errors and eligible == len(rows)
        else "BLOCKED",
        "food_rows": len(rows),
        "schema_valid_rows": len(records),
        "approved_rows": sum(row["review_status"] == "approved" for row in records),
        "eligible_rows": eligible,
        "target_food_rows": 48,
        "data_quality_counts": quality,
        "synthetic_rows": sum(row["is_synthetic"] for row in records),
        "records": records,
        "errors": errors,
    }
