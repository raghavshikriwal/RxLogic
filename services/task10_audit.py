"""Task 10 clinical validation protocol and software-safety audit."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from models.schemas import Medication
from services.clinical_reasoning import ClinicalReasoningEngine, DOMAINS
from services.clinical_validation import validate_validation_dataset, reviewer_agreement

DEFAULT_KNOWLEDGE_ROOT = Path(__file__).resolve().parent.parent / "knowledge"
DEFAULT_CASES_PATH = DEFAULT_KNOWLEDGE_ROOT / "clinical_validation_cases.json"


def build_task10_audit(knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
                       cases_path: Path | None = None) -> dict[str, Any]:
    root = Path(knowledge_root)
    case_file = Path(cases_path) if cases_path else root / "clinical_validation_cases.json"
    assertions = json.loads((root / "clinical_assertions.json").read_text(encoding="utf-8"))
    cases_payload = json.loads(case_file.read_text(encoding="utf-8"))
    assertion_ids = {str(row.get("assertion_id")) for domain in DOMAINS
                     for row in assertions.get(domain, []) if isinstance(row, dict)}
    evidence_payload = json.loads((root / "evidence_sources.json").read_text(encoding="utf-8"))
    source_ids = {str(row.get("source_id")) for row in evidence_payload.get("sources", []) if isinstance(row, dict)}
    dataset_errors = validate_validation_dataset(cases_payload, assertion_ids=assertion_ids, source_ids=source_ids)
    cases = cases_payload.get("cases", []) if isinstance(cases_payload, dict) else []
    clinical_cases = [c for c in cases if isinstance(c, dict) and c.get("case_type") == "clinical_reference"]
    adjudicated = [c for c in clinical_cases if c.get("adjudication_state") == "adjudicated"]

    engine = ClinicalReasoningEngine(assertions=assertions)
    probe = engine.assess([Medication(name="rxlogic-task10-safety-probe")])
    runtime_checks = {
        "no_unapproved_findings_emitted": probe.get("findings") == [],
        "empty_knowledge_fails_closed": probe.get("status") == "insufficient_approved_knowledge",
        "missing_knowledge_not_declared_safe": "not evidence" in probe.get("interpretation", "").lower(),
        "patient_specific_dose_not_generated": probe.get("dosage_safety", {}).get("patient_specific_dosing_generated") is False,
        "clinical_use_not_permitted": probe.get("clinical_use_permitted") is False,
    }
    structure_checks = {
        "validation_dataset_schema_valid": not dataset_errors,
        "no_unreviewed_case_counted_as_adjudicated": len(adjudicated) <= len(clinical_cases),
        "reviewer_ids_present_for_adjudicated_cases": all(
            len({d.get("reviewer_id") for d in c.get("reviewer_decisions", [])}) >= 2 for c in adjudicated
        ),
    }
    return {
        "schema_version": "1.0.0",
        "audit_type": "task10_clinical_validation_protocol_and_software_safety_audit",
        "passed": all(runtime_checks.values()) and all(structure_checks.values()),
        "checks": {**runtime_checks, **structure_checks},
        "validation_dataset_errors": dataset_errors,
        "case_counts": {"total": len(cases), "clinical_reference": len(clinical_cases),
                        "adjudicated_clinical_reference": len(adjudicated),
                        "software_invariant": sum(1 for c in cases if isinstance(c, dict) and c.get("case_type") == "software_invariant")},
        "reviewer_agreement": reviewer_agreement(adjudicated),
        "clinical_performance_metrics": None if not adjudicated else {
            "status": "not_computed_without_saved_model_predictions",
            "reason": "Run a versioned evaluation against adjudicated cases before reporting clinical metrics."
        },
        "runtime_probe": {"status": probe.get("status"), "finding_count": len(probe.get("findings", [])),
                          "clinical_use_permitted": probe.get("clinical_use_permitted"),
                          "dosage_safety": probe.get("dosage_safety", {})},
        "clinical_validation_status": "not_performed" if not adjudicated else "reference_cases_adjudicated_pending_model_evaluation",
        "limitations": [
            "This audit verifies software behavior and validation-data governance; it does not establish clinical correctness.",
            "No clinical reference cases or adjudicated labels are fabricated or bundled.",
            "Reviewer role strings are not identity or credential authentication.",
            "Clinical performance metrics require independent adjudication and versioned model predictions.",
            "Clinical use remains prohibited unless separately authorized through appropriate governance and validation."
        ],
    }
