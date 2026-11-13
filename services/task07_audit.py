"""Deterministic structural/governance audit for Task 07 knowledge data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.knowledge_coverage import build_coverage_report
from services.knowledge_validation import validate_knowledge


def build_task07_audit(knowledge_root: Path) -> dict[str, Any]:
    root = Path(knowledge_root)
    errors = validate_knowledge(root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    clinical = json.loads((root / "clinical_assertions.json").read_text(encoding="utf-8"))
    coverage = build_coverage_report(root)
    policy = manifest.get("publication_policy", {})
    clinical_counts = {
        domain: len(clinical.get(domain, []))
        for domain in ("drug_food_interactions", "contraindications", "dosage_references", "administration_instructions")
    }
    unsafe_patient_specific_dose_records = [
        row.get("assertion_id") for row in clinical.get("dosage_references", [])
        if row.get("patient_specific") is not False
    ]
    unapproved_runtime_records = [
        row.get("assertion_id")
        for domain in clinical_counts
        for row in clinical.get(domain, [])
        if row.get("review_status") != "clinically_approved"
    ]
    checks = {
        "knowledge_structurally_valid": not errors,
        "development_runtime_policy_is_explicit": (
            manifest.get("release_status") == "development_unreviewed"
            and policy.get("runtime_may_load_unreviewed_records") is True
        ) or policy.get("runtime_may_load_unreviewed_records") is False,
        "clinical_use_prohibited": policy.get("clinical_use_permitted") is False,
        "dosage_records_are_non_patient_specific": not unsafe_patient_specific_dose_records,
        "no_unapproved_clinical_assertions": not unapproved_runtime_records,
    }
    return {
        "schema_version": "1.0.0",
        "audit_type": "task07_knowledge_governance_structural_audit_not_clinical_validation",
        "knowledge_release": manifest.get("knowledge_release"),
        "passed": all(checks.values()),
        "checks": checks,
        "validation_errors": errors,
        "clinical_assertion_counts": clinical_counts,
        "unsafe_patient_specific_dosage_assertion_ids": unsafe_patient_specific_dose_records,
        "unapproved_clinical_assertion_ids": unapproved_runtime_records,
        "clinical_assertions_are_empty_pending_review": sum(clinical_counts.values()) == 0,
        "clinical_assertion_records_present": sum(clinical_counts.values()) > 0,
        "coverage_summary": {
            "medication_count": coverage["medication_count"],
            "drug_drug_interactions": coverage["drug_drug_interactions"]["counts"],
            "drug_food_guidance": coverage["drug_food_guidance"]["counts"],
            "contraindications": coverage["contraindications"]["counts"],
            "dosage_references": coverage["dosage_references"]["counts"],
            "administration_instructions": coverage["administration_instructions"]["counts"],
            "drug_food_component_interactions": coverage["drug_food_interactions"]["counts"],
        },
        "limitations": [
            "This is a structural and governance audit, not clinical validation.",
            "Coverage gaps are not negative findings and must not be interpreted as safety.",
            "New clinical assertion datasets are not yet consumed by patient-plan reasoning.",
            "Local CLI actor roles are audit assertions, not authenticated staff identities.",
            "No clinical-use authorization is granted by this audit.",
        ],
    }
