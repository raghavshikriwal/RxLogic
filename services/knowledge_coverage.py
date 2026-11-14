"""Evidence-aware coverage inventory for the curated medication knowledge base.

This module reports what has and has not been evaluated. It deliberately does
not infer that a missing assertion means a combination is safe or has no
interaction. It is an inventory tool, not a clinical decision engine.
"""
from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Any

from services.clinical_knowledge import ALL_DOMAINS, DOMAINS, EXTENDED_DOMAINS, classify_assertion

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge"

ASSERTION_PRESENT = "assertion_present_unreviewed"
NOT_EVALUATED = "not_evaluated"
CONFLICTING = "conflicting_evidence"
REVIEWED = "assertion_present_reviewed"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def _source_verification_state(source: dict[str, Any]) -> str:
    """Return the recorded verification state without inferring source quality."""
    status = source.get("verification_status")
    return str(status).strip() if isinstance(status, str) and status.strip() else "not_recorded"


def _assertion_state(record: dict[str, Any]) -> str:
    review = str(record.get("review_status", "needs_clinical_review")).lower()
    if record.get("evidence_status") == CONFLICTING or record.get("conflicting_evidence") is True:
        return CONFLICTING
    if review in {"reviewed", "clinically_approved"}:
        return REVIEWED
    return ASSERTION_PRESENT


def _source_summary(source_ids: list[str], source_map: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    result = []
    for source_id in source_ids:
        source = source_map.get(source_id, {})
        result.append({
            "source_id": source_id,
            "source_verification_state": _source_verification_state(source),
            "source_quality_assessment": str(source.get("source_quality_assessment", "not_assessed")),
            "source_quality_tier": str(source.get("source_quality_tier", "not_assessed")),
            "source_quality_assessments": list(source.get("source_quality_assessments", [])),
        })
    return result


def build_coverage_report(knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT) -> dict[str, Any]:
    """Build a deterministic, evidence-aware coverage report.

    Counts are denominated against the medication list in the development
    dataset. Empty domains mean not assessed, never that the absence of risk
    has been established.
    """
    root = Path(knowledge_root)
    interactions = _read_json(root / "interaction_rules.json")
    foods = _read_json(root / "food_rules.json")
    evidence = _read_json(root / "evidence_sources.json")
    clinical_path = root / "clinical_assertions.json"
    clinical = _read_json(clinical_path) if clinical_path.exists() else {}

    medication_map = interactions.get("medications", {})
    medications = sorted({str(name).strip().lower() for name in medication_map if str(name).strip()})
    source_map = {
        str(item.get("source_id")): item
        for item in evidence.get("sources", [])
        if isinstance(item, dict) and item.get("source_id")
    }

    def counts(records: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "total": len(records),
            "assertion_present_unreviewed": sum(row["status"] == ASSERTION_PRESENT for row in records),
            "assertion_present_reviewed": sum(row["status"] == REVIEWED for row in records),
            "not_evaluated": sum(row["status"] == NOT_EVALUATED for row in records),
            "conflicting_evidence": sum(row["status"] == CONFLICTING for row in records),
        }

    pair_groups: dict[frozenset[str], list[dict[str, Any]]] = {}
    for rule in interactions.get("interaction_rules", []):
        a, b = str(rule.get("medication_a", "")).lower(), str(rule.get("medication_b", "")).lower()
        if a and b and a != b:
            pair_groups.setdefault(frozenset((a, b)), []).append(rule)
    ddi_pairs = []
    for a, b in combinations(medications, 2):
        matches = pair_groups.get(frozenset((a, b)), [])
        if not matches:
            ddi_pairs.append({"medication_a": a, "medication_b": b, "status": NOT_EVALUATED, "rule_id": None, "evidence": []})
        elif len(matches) > 1:
            ddi_pairs.append({"medication_a": a, "medication_b": b, "status": CONFLICTING, "rule_id": None,
                              "duplicate_assertion_count": len(matches), "evidence": []})
        else:
            rule = matches[0]
            refs = list(rule.get("evidence_source_ids", []))
            ddi_pairs.append({"medication_a": a, "medication_b": b, "status": _assertion_state(rule),
                              "rule_id": rule.get("rule_id"), "evidence_strength": rule.get("evidence_strength", rule.get("evidence", "unknown")),
                              "evidence": _source_summary(refs, source_map)})

    food_groups: dict[str, list[dict[str, Any]]] = {}
    for rule in foods.get("food_rules", []):
        food_groups.setdefault(str(rule.get("medication", "")).lower(), []).append(rule)
    food_coverage = []
    for medication in medications:
        matches = food_groups.get(medication, [])
        if not matches:
            food_coverage.append({"medication": medication, "status": NOT_EVALUATED, "rule_id": None, "evidence": []})
        elif len(matches) > 1:
            food_coverage.append({"medication": medication, "status": CONFLICTING, "rule_id": None, "duplicate_assertion_count": len(matches), "evidence": []})
        else:
            rule = matches[0]
            food_coverage.append({"medication": medication, "status": _assertion_state(rule), "rule_id": rule.get("rule_id"),
                                  "evidence": _source_summary(list(rule.get("evidence_source_ids", [])), source_map)})

    clinical_domains: dict[str, Any] = {}
    for domain in ALL_DOMAINS:
        assertions = clinical.get(domain, []) if isinstance(clinical.get(domain, []), list) else []
        rows = []
        by_medication: dict[str, list[dict[str, Any]]] = {}
        for assertion in assertions:
            if isinstance(assertion, dict):
                by_medication.setdefault(str(assertion.get("medication", "")).lower(), []).append(assertion)
        for medication in medications:
            records = by_medication.get(medication, [])
            if not records:
                rows.append({"medication": medication, "status": NOT_EVALUATED, "assertion_count": 0, "assertions": []})
            else:
                states = {classify_assertion(record) for record in records}
                state = CONFLICTING if "conflicting_evidence" in states else (REVIEWED if states == {REVIEWED} else ASSERTION_PRESENT)
                rows.append({"medication": medication, "status": state, "assertion_count": len(records),
                             "assertions": [{"assertion_id": record.get("assertion_id"),
                                             "evidence_strength": record.get("evidence_strength", "unknown"),
                                             "source_quality_tier": record.get("source_quality_tier", "not_assessed"),
                                             "conflict_status": record.get("conflict_status", "not_assessed"),
                                             "evidence": _source_summary(list(record.get("evidence_source_ids", [])), source_map)}
                                            for record in records]})
        clinical_domains[domain] = {"counts": counts(rows), "medications": rows}

    return {
        "schema_version": "1.2.0",
        "knowledge_release": interactions.get("knowledge_release", "unknown"),
        "inventory_type": "development_knowledge_coverage_not_clinical_validation",
        "medication_count": len(medications),
        "drug_drug_interactions": {"counts": counts(ddi_pairs), "pairs": ddi_pairs},
        "drug_food_guidance": {"counts": counts(food_coverage), "medications": food_coverage},
        "drug_food_interactions": {
            **clinical_domains["drug_food_interactions"],
            "enumeration_status": "medication_level_only",
            "component_denominator": None,
            "reason": "A governed food/component taxonomy has not been established; counts indicate whether a medication has any recorded assertion, not exhaustive ingredient-pair coverage.",
        },
        "contraindications": clinical_domains["contraindications"],
        "dosage_references": clinical_domains["dosage_references"],
        "administration_instructions": clinical_domains["administration_instructions"],
        "monograph_domains": {domain: clinical_domains[domain] for domain in EXTENDED_DOMAINS},
        "evidence_appraisal": {
            "source_count": len(source_map),
            "source_quality_assessed": sum(bool(item.get("source_quality_assessments")) or bool(item.get("source_quality_tier") and item.get("source_quality_tier") != "not_assessed") for item in source_map.values()),
            "source_quality_not_assessed": sum(not item.get("source_quality_assessments") and (not item.get("source_quality_tier") or item.get("source_quality_tier") == "not_assessed") for item in source_map.values()),
            "note": "Source identity/integrity, source quality, and assertion evidence strength are distinct attributes.",
        },
        "interpretation": [
            "not_evaluated means no assessment is recorded; it does not mean no interaction, no contraindication, or safe use.",
            "assertion_present_unreviewed means an assertion exists but has not passed independent clinical approval.",
            "conflicting_evidence requires explicit resolution; the report does not choose one source automatically.",
            "Dosage references are source summaries, not patient-specific prescriptions or dose calculations.",
            "This report describes the shipped development dataset only; it is not an exhaustive drug-safety assessment.",
        ],
    }


def main() -> int:
    report = build_coverage_report()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
