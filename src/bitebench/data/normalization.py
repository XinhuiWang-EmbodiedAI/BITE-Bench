"""FDC nutrient ID mapping with source units and energy basis retained."""

import math

from bitebench.nutrition.units import convert

NUTRIENTS = {
    1003: ("protein_g_per_100g", "g"),
    1004: ("fat_g_per_100g", "g"),
    1005: ("carbs_g_per_100g", "g"),
    1079: ("fiber_g_per_100g", "g"),
    1093: ("sodium_mg_per_100g", "mg"),
}
# Legacy energy, Atwater general, Atwater specific, legacy kJ fallback.
ENERGY_IDS = [1008, 2047, 2048, 1062]
FIELDS = ["energy_kcal_per_100g", *[field for field, _ in NUTRIENTS.values()]]


def normalize_fdc(snapshot: dict) -> dict:
    food = snapshot["response"]
    data_type = food.get("dataType")
    result = {name: None for name in FIELDS}
    issues, audit, energies = [], [], {}
    conflicts = set()
    basis_known = data_type in {"Foundation", "SR Legacy", "Survey (FNDDS)"} or (
        data_type == "Branded" and str(food.get("servingSizeUnit", "")).lower() == "g"
    )
    if not basis_known:
        return {
            "nutrients": result,
            "issues": ["UNKNOWN_NUTRIENT_BASIS"],
            "audit": [],
            "source_record_id": str(food.get("fdcId", "")),
            "source_url": f"https://fdc.nal.usda.gov/food-details/{food.get('fdcId')}/nutrients",
            "retrieved_at": snapshot.get("retrieved_at"),
            "is_synthetic": bool(food.get("is_synthetic", False)),
        }
    for row in food.get("foodNutrients", []):
        nutrient = row.get("nutrient", row)
        identifier = nutrient.get("id", row.get("nutrientId"))
        try:
            identifier = int(identifier)
        except (ValueError, TypeError):
            continue
        mapping = (
            ("energy_kcal_per_100g", "kcal")
            if identifier in ENERGY_IDS
            else NUTRIENTS.get(identifier)
        )
        if not mapping:
            continue
        field, target = mapping
        raw = row.get("amount", row.get("value"))
        unit = nutrient.get("unitName", row.get("unitName", ""))
        expected_unit = "kj" if identifier == 1062 else target
        if raw is None:
            continue
        try:
            if identifier in ENERGY_IDS and unit.lower() != expected_unit:
                raise ValueError("energy ID/unit mismatch")
            value = convert(float(raw), unit, target)
        except (ValueError, TypeError, AttributeError):
            issues.append(f"INVALID_UNIT_OR_VALUE:{identifier}")
            continue
        if row.get("loq") is not None and value == 0:
            try:
                if float(row["loq"]) > 0:
                    issues.append(f"BELOW_LOQ:{identifier}")
                    value = None
            except (ValueError, TypeError):
                issues.append(f"INVALID_LOQ:{identifier}")
                value = None
        audit.append(
            {
                "nutrient_id": identifier,
                "source_value": raw,
                "source_unit": unit,
                "basis": "per_100g",
                "target_field": field,
                "target_unit": target,
                "converted_value": value,
                "source_loq": row.get("loq"),
            }
        )
        target_dict = energies if identifier in ENERGY_IDS else result
        key = identifier if identifier in ENERGY_IDS else field
        if value is None:
            target_dict[key] = None
            conflicts.add(key)
            continue
        if key in conflicts:
            continue
        if target_dict.get(key) is not None and not math.isclose(
            target_dict[key], value, abs_tol=1e-6
        ):
            issues.append(f"CONFLICTING_VALUES:{identifier}")
            target_dict[key] = None
            conflicts.add(key)
        else:
            target_dict[key] = value
    energy_id = next((key for key in ENERGY_IDS if energies.get(key) is not None), None)
    result["energy_kcal_per_100g"] = energies.get(energy_id)
    if len(energies) > 1:
        issues.append("MULTIPLE_ENERGY_BASES_REVIEW")
    energy = result["energy_kcal_per_100g"]
    if energy is not None and energy > 900:
        issues.append("EXTREME_ENERGY_DENSITY_REVIEW")
    if any(
        value is not None and value > 100
        for key, value in result.items()
        if key.endswith("_g_per_100g")
    ):
        issues.append("EXTREME_MACRONUTRIENT_DENSITY_REVIEW")
    macros = [
        result[key]
        for key in ("protein_g_per_100g", "fat_g_per_100g", "carbs_g_per_100g")
    ]
    if energy is not None and all(value is not None for value in macros):
        estimate = 4 * macros[0] + 9 * macros[1] + 4 * macros[2]
        if abs(energy - estimate) > max(20, 0.5 * energy):
            issues.append("MACRO_ENERGY_CHECK_REVIEW")
    issues += [f"MISSING:{name}" for name, value in result.items() if value is None]
    return {
        "nutrients": result,
        "issues": sorted(set(issues)),
        "audit": audit,
        "energy_nutrient_id": energy_id,
        "source_record_id": str(food.get("fdcId", "")),
        "source_url": f"https://fdc.nal.usda.gov/food-details/{food.get('fdcId')}/nutrients",
        "source_description": food.get("description"),
        "source_data_type": data_type,
        "retrieved_at": snapshot.get("retrieved_at"),
        "data_quality": "database",
        "is_synthetic": bool(food.get("is_synthetic", False)),
    }
