"""Evidence-governed clinical assertion evaluation (Task 09).

This service consumes only explicitly approved assertions with an explicit,
acceptable conflict assessment. It never infers a negative finding from missing
knowledge and never converts dosage references into patient-specific advice.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from models.schemas import Medication

DEFAULT_ASSERTIONS_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "clinical_assertions.json"
DOMAINS = (
    "drug_food_interactions", "contraindications", "dosage_references",
    "administration_instructions",
)


def _tokens(values: Iterable[str] | None) -> set[str]:
    return {str(value).strip().casefold() for value in (values or ()) if str(value).strip()}


def _is_usable(record: dict[str, Any]) -> bool:
    return (
        record.get("review_status") == "clinically_approved"
        and record.get("conflict_status") in {"no_known_conflict", "resolved"}
        and isinstance(record.get("evidence_source_ids"), list)
        and bool(record["evidence_source_ids"])
        and all(isinstance(ref, str) and ref.strip() for ref in record["evidence_source_ids"])
        and (record.get("conflict_status") != "resolved" or bool(str(record.get("conflict_resolution", "")).strip()))
    )


class ClinicalReasoningEngine:
    """Match user-supplied context against governed assertions, without inference."""

    def __init__(self, assertions: dict[str, Any] | None = None, path: Path = DEFAULT_ASSERTIONS_PATH):
        if assertions is None:
            assertions = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(assertions, dict):
            raise ValueError("clinical assertions dataset must be an object")
        self.assertions = assertions
        for domain in DOMAINS:
            if not isinstance(assertions.get(domain), list):
                raise ValueError(f"clinical assertions domain {domain!r} must be an array")

    def assess(
        self,
        medications: list[Medication],
        *,
        foods: Iterable[str] | None = None,
        conditions: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        medication_names = _tokens(m.name for m in medications)
        food_context = _tokens(foods)
        condition_context = _tokens(conditions)
        findings: list[dict[str, Any]] = []
        domain_summary: dict[str, dict[str, Any]] = {}
        unresolved_conflicts: list[dict[str, str]] = []
        excluded_counts: dict[str, int] = {}

        for domain in DOMAINS:
            records = self.assertions[domain]
            usable = [r for r in records if isinstance(r, dict) and _is_usable(r)]
            excluded = [r for r in records if isinstance(r, dict) and not _is_usable(r)]
            excluded_counts[domain] = len(excluded)
            for record in excluded:
                if record.get("conflict_status") == "conflicting_evidence":
                    unresolved_conflicts.append({
                        "assertion_id": str(record.get("assertion_id", "unknown")),
                        "domain": domain,
                        "medication": str(record.get("medication", "unknown")),
                        "status": "conflicting_evidence",
                    })

            matched = []
            context_missing = False
            for record in usable:
                med = str(record.get("medication", "")).strip().casefold()
                if med not in medication_names:
                    continue
                if domain == "drug_food_interactions":
                    if not food_context:
                        context_missing = True
                        continue
                    if str(record.get("food_or_component", "")).strip().casefold() not in food_context:
                        continue
                    message = str(record.get("clinical_effect", ""))
                    matched.append(self._finding(record, domain, message))
                elif domain == "contraindications":
                    if not condition_context:
                        context_missing = True
                        continue
                    target = str(record.get("condition_or_population", "")).strip().casefold()
                    if target not in condition_context:
                        continue
                    message = str(record.get("clinical_action", ""))
                    matched.append(self._finding(record, domain, message))
                elif domain == "administration_instructions":
                    matched.append(self._finding(record, domain, str(record.get("instruction", ""))))
                # Dosage references are deliberately not emitted as instructions.
            findings.extend(matched)

            if domain == "drug_food_interactions" and not food_context:
                status = "context_not_supplied" if any(str(r.get("medication", "")).casefold() in medication_names for r in usable) else "no_approved_assertions"
            elif domain == "contraindications" and not condition_context:
                status = "context_not_supplied" if any(str(r.get("medication", "")).casefold() in medication_names for r in usable) else "no_approved_assertions"
            elif matched:
                status = "approved_findings_present"
            elif usable:
                status = "no_matching_approved_assertion"
            else:
                status = "no_approved_assertions"
            domain_summary[domain] = {
                "status": status,
                "approved_assertions_available": len(usable),
                "matched_findings": len(matched),
                "excluded_unapproved_or_conflicted": len(excluded),
                "context_supplied": (
                    bool(food_context) if domain == "drug_food_interactions"
                    else bool(condition_context) if domain == "contraindications"
                    else None
                ),
            }

        dosage_records = [r for r in self.assertions["dosage_references"] if isinstance(r, dict) and _is_usable(r)]
        matched_dosage_references = sum(
            str(r.get("medication", "")).strip().casefold() in medication_names for r in dosage_records
        )
        return {
            "status": "approved_findings_present" if findings else "insufficient_approved_knowledge",
            "findings": findings,
            "domains": domain_summary,
            "unresolved_conflicts": unresolved_conflicts,
            "excluded_assertion_counts": excluded_counts,
            "dosage_safety": {
                "status": "reference_only_not_a_prescription",
                "matching_approved_reference_count": matched_dosage_references,
                "patient_specific_dosing_generated": False,
                "message": "RxLogic does not calculate, select, or recommend a patient-specific dose.",
            },
            "interpretation": (
                "Approved findings are limited to the supplied context and available reviewed evidence."
                if findings else
                "No approved finding was produced. Missing, unreviewed, rejected, withdrawn, or conflicting knowledge is not evidence that a medication combination is safe."
            ),
            "clinical_use_permitted": False,
        }

    @staticmethod
    def _finding(record: dict[str, Any], domain: str, message: str) -> dict[str, Any]:
        return {
            "assertion_id": str(record.get("assertion_id", "")),
            "domain": domain,
            "medication": str(record.get("medication", "")),
            "message": message,
            "severity": record.get("severity", "unknown"),
            "evidence_strength": record.get("evidence_strength", "unknown"),
            "source": str(record.get("source", "")),
            "evidence_source_ids": list(record.get("evidence_source_ids", [])),
            "jurisdiction": str(record.get("jurisdiction", "unspecified")),
            "review_status": "clinically_approved",
            "is_patient_specific_recommendation": False,
        }
