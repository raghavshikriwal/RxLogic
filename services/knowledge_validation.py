"""
Offline structural validation for the versioned RxLogic knowledge release.

This validates data integrity and provenance links, not clinical correctness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.clinical_knowledge import validate_clinical_assertions

ROOT = Path(__file__).resolve().parent.parent / "knowledge"
ALLOWED_REVIEW_STATES = {"needs_clinical_review", "reviewed", "rejected", "withdrawn"}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name}: root must be a JSON object")
    return value


def validate_knowledge(root: Path = ROOT) -> list[str]:
    """Return all structural errors; an empty list means structurally valid."""
    errors: list[str] = []
    manifest = _load(root / "manifest.json")
    interactions = _load(root / "interaction_rules.json")
    foods = _load(root / "food_rules.json")
    evidence = _load(root / "evidence_sources.json")
    clinical_path = root / "clinical_assertions.json"
    clinical = _load(clinical_path) if clinical_path.exists() else {
        "schema_version": "1.0.0", "drug_food_interactions": [],
        "contraindications": [], "dosage_references": [], "administration_instructions": [],
    }

    release = manifest.get("knowledge_release")
    if not release:
        errors.append("manifest: knowledge_release is required")
    declared_datasets = manifest.get("datasets")
    clinical_declaration = declared_datasets.get("clinical_assertions") if isinstance(declared_datasets, dict) else None
    if not isinstance(clinical_declaration, dict) or clinical_declaration.get("path") != "clinical_assertions.json" or clinical_declaration.get("schema_version") != "1.0.0":
        errors.append("manifest: clinical_assertions dataset must declare path clinical_assertions.json and schema_version 1.0.0")
    for name, dataset in (("interaction_rules", interactions), ("food_rules", foods)):
        if dataset.get("schema_version") != "2.0.0":
            errors.append(f"{name}: expected schema_version 2.0.0")
        if dataset.get("knowledge_release") != release:
            errors.append(f"{name}: knowledge_release does not match manifest")

    source_ids = [s.get("source_id") for s in evidence.get("sources", [])]
    if any(not sid for sid in source_ids):
        errors.append("evidence_sources: every source requires source_id")
    if len(source_ids) != len(set(source_ids)):
        errors.append("evidence_sources: duplicate source_id")
    source_set = set(source_ids)

    medications = {str(k).lower() for k in interactions.get("medications", {})}
    if clinical.get("knowledge_release") != release:
        errors.append("clinical_assertions: knowledge_release does not match manifest")
    errors.extend(validate_clinical_assertions(clinical, medications, source_set))
    seen_rule_ids: set[str] = set()
    seen_pairs: set[frozenset[str]] = set()
    for index, rule in enumerate(interactions.get("interaction_rules", [])):
        prefix = f"interaction_rules[{index}]"
        rid = rule.get("rule_id")
        if not rid:
            errors.append(f"{prefix}: rule_id is required")
        elif rid in seen_rule_ids:
            errors.append(f"{prefix}: duplicate rule_id {rid}")
        else:
            seen_rule_ids.add(rid)
        a, b = str(rule.get("medication_a", "")).lower(), str(rule.get("medication_b", "")).lower()
        if not a or not b or a == b:
            errors.append(f"{prefix}: medication pair must contain two distinct names")
        pair = frozenset((a, b))
        if pair in seen_pairs:
            errors.append(f"{prefix}: duplicate medication pair {sorted(pair)}")
        seen_pairs.add(pair)
        if a not in medications or b not in medications:
            errors.append(f"{prefix}: both medications must exist in medication map")
        if rule.get("review_status") not in ALLOWED_REVIEW_STATES:
            errors.append(f"{prefix}: invalid or missing review_status")
        refs = rule.get("evidence_source_ids", [])
        if not refs:
            errors.append(f"{prefix}: at least one evidence_source_id is required")
        for ref in refs:
            if ref not in source_set:
                errors.append(f"{prefix}: unknown evidence source {ref!r}")

    seen_food: set[str] = set()
    for index, rule in enumerate(foods.get("food_rules", [])):
        prefix = f"food_rules[{index}]"
        name, rid = str(rule.get("medication", "")).lower(), rule.get("rule_id")
        if name in seen_food:
            errors.append(f"{prefix}: duplicate food rule for {name!r}")
        seen_food.add(name)
        if name not in medications:
            errors.append(f"{prefix}: medication {name!r} is not in medication map")
        if not rid or rid in seen_rule_ids:
            errors.append(f"{prefix}: missing or duplicate rule_id {rid!r}")
        elif rid:
            seen_rule_ids.add(rid)
        if rule.get("review_status") not in ALLOWED_REVIEW_STATES:
            errors.append(f"{prefix}: invalid or missing review_status")
        refs = rule.get("evidence_source_ids", [])
        if not refs:
            errors.append(f"{prefix}: at least one evidence_source_id is required")
        for ref in refs:
            if ref not in source_set:
                errors.append(f"{prefix}: unknown evidence source {ref!r}")

    return errors


def main() -> int:
    errors = validate_knowledge()
    if errors:
        print("Knowledge validation FAILED:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Knowledge validation PASSED (structural integrity only; not clinical validation).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
