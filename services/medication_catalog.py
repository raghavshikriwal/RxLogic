"""Validated medication identity catalog (not a clinical knowledge source).

Catalog records identify ingredients and accepted names. They never imply that
interaction, food-effect, contraindication, dosage, or administration evidence
has been evaluated for that medication.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "knowledge" / "medication_catalog.json"
_NAME = re.compile(r"^[a-z][a-z0-9 .'-]{1,99}$")
_RXCUI = re.compile(r"^[0-9]{1,12}$")

COVERAGE_STATUSES = frozenset({
    "identity_only_not_evaluated",
    "legacy_assertions_unreviewed_partial",
    "cited_assertions_unreviewed_partial",
})
IDENTITY_STATUSES = frozenset({
    "existing_catalog_entry",
    "added_task08_identity_only",
    "added_task13_rule_expansion",
})
# Entries added after the original catalog must say where their identity came from.
IDENTITY_STATUSES_REQUIRING_REFERENCE = IDENTITY_STATUSES - {"existing_catalog_entry"}


class MedicationCatalogError(ValueError):
    """Raised when the identity catalog is malformed or inconsistent."""


def validate_medication_catalog(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["catalog must be a JSON object"]
    if payload.get("schema_version") != "1.0.0":
        errors.append("unsupported medication catalog schema_version")
    if payload.get("clinical_use_permitted") is not False:
        errors.append("clinical_use_permitted must be false")
    source = payload.get("identity_source")
    if not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://"):
        errors.append("identity_source must include an HTTPS URL")
    rows = payload.get("medications")
    if not isinstance(rows, list) or not rows:
        return errors + ["medications must be a non-empty array"]
    canonical: set[str] = set()
    rxcuis: set[str] = set()
    terms: dict[str, str] = {}
    for index, row in enumerate(rows):
        prefix = f"medications[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix} must be an object")
            continue
        name = row.get("canonical_name")
        rxcui = str(row.get("rxcui", ""))
        if not isinstance(name, str) or not _NAME.fullmatch(name) or name != name.casefold():
            errors.append(f"{prefix}.canonical_name must be a lowercase ingredient name")
            continue
        if name in canonical:
            errors.append(f"duplicate canonical_name: {name}")
        canonical.add(name)
        if not _RXCUI.fullmatch(rxcui):
            errors.append(f"{prefix}.rxcui must be a numeric RxCUI")
        elif rxcui in rxcuis:
            errors.append(f"duplicate RxCUI: {rxcui}")
        rxcuis.add(rxcui)
        aliases = row.get("aliases", [])
        if not isinstance(aliases, list):
            errors.append(f"{prefix}.aliases must be an array")
            continue
        for alias in aliases:
            if not isinstance(alias, str) or not _NAME.fullmatch(alias) or alias != alias.casefold():
                errors.append(f"{prefix} contains an invalid lowercase alias")
                continue
            if alias in terms or alias in canonical:
                errors.append(f"duplicate or colliding medication term: {alias}")
            terms[alias] = name
        if row.get("clinical_coverage_status") not in COVERAGE_STATUSES:
            errors.append(f"{prefix}.clinical_coverage_status is invalid")
        if row.get("identity_status") not in IDENTITY_STATUSES:
            errors.append(f"{prefix}.identity_status is invalid")
        if row.get("identity_status") in IDENTITY_STATUSES_REQUIRING_REFERENCE and not str(row.get("identity_reference", "")).startswith("https://"):
            errors.append(f"{prefix}.identity_reference must be HTTPS")
    for term in terms:
        if term in canonical:
            errors.append(f"alias collides with canonical medication name: {term}")
    return errors


def load_medication_catalog(path: Path = DEFAULT_CATALOG_PATH) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MedicationCatalogError(f"cannot load medication catalog: {exc}") from exc
    errors = validate_medication_catalog(payload)
    if errors:
        raise MedicationCatalogError("; ".join(errors))
    return payload


def catalog_maps(payload: dict[str, Any] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """Return canonical-name -> RxCUI and alias -> canonical-name maps."""
    data = payload or load_medication_catalog()
    rxcuis: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for row in data["medications"]:
        name = row["canonical_name"]
        rxcuis[name] = str(row["rxcui"])
        for alias in row.get("aliases", []):
            aliases[alias] = name
    return rxcuis, aliases


def audit_catalog_against_runtime(catalog_path: Path, interaction_rules_path: Path) -> dict[str, Any]:
    catalog = load_medication_catalog(catalog_path)
    try:
        runtime = json.loads(Path(interaction_rules_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MedicationCatalogError(f"cannot load interaction rules: {exc}") from exc
    catalog_map = {row["canonical_name"]: str(row["rxcui"]) for row in catalog["medications"]}
    runtime_map = {str(k).casefold(): str(v) for k, v in runtime.get("medications", {}).items()}
    missing = sorted(set(catalog_map) - set(runtime_map))
    mismatched = sorted(name for name in catalog_map.keys() & runtime_map.keys() if catalog_map[name] != runtime_map[name])
    extra = sorted(set(runtime_map) - set(catalog_map))
    return {
        "catalog_medication_count": len(catalog_map),
        "runtime_medication_count": len(runtime_map),
        "catalog_entries_missing_from_runtime": missing,
        "rxcui_mismatches": mismatched,
        "runtime_entries_missing_from_catalog": extra,
        "passed": not (missing or mismatched or extra),
    }
