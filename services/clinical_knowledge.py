"""Typed validation helpers for Task 07 clinical knowledge assertions.

This module validates structure and governance metadata only. It does not
adjudicate clinical truth, calculate a patient-specific dose, or infer safety.
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1.0.0"
DOMAINS = (
    "drug_food_interactions", "contraindications", "dosage_references",
    "administration_instructions",
)
EVIDENCE_STRENGTHS = frozenset({"strong", "moderate", "limited", "unknown"})
SEVERITIES = frozenset({"mild", "moderate", "severe", "unknown"})
SOURCE_TYPES = frozenset({"fda_label", "rxnorm_concept", "dailymed_spl", "clinical_guideline", "systematic_review", "regulatory_notice", "other"})
SOURCE_QUALITY_TIERS = frozenset({
    "high", "moderate", "low", "not_assessed",
})
REVIEW_STATES = frozenset({"needs_clinical_review", "clinically_approved", "rejected", "withdrawn"})
CONFLICT_STATES = frozenset({"not_assessed", "no_known_conflict", "conflicting_evidence", "resolved"})


class ClinicalKnowledgeValidationError(ValueError):
    """Raised for malformed Task 07 knowledge datasets."""


def validate_clinical_assertions(
    payload: dict[str, Any], medication_names: set[str] | None = None,
    source_ids: set[str] | None = None,
) -> list[str]:
    """Return structural errors for a clinical_assertions.json document."""
    errors: list[str] = []
    seen_assertion_ids: set[str] = set()
    if not isinstance(payload, dict):
        return ["clinical_assertions: root must be an object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"clinical_assertions: schema_version must be {SCHEMA_VERSION}")
    for domain in DOMAINS:
        records = payload.get(domain)
        if not isinstance(records, list):
            errors.append(f"clinical_assertions: {domain} must be an array")
            continue
        for index, record in enumerate(records):
            prefix = f"clinical_assertions.{domain}[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{prefix}: record must be an object")
                continue
            assertion_id = record.get("assertion_id")
            if not isinstance(assertion_id, str) or not assertion_id.strip():
                errors.append(f"{prefix}: assertion_id is required")
            elif assertion_id in seen_assertion_ids:
                errors.append(f"{prefix}: duplicate assertion_id {assertion_id}")
            else:
                seen_assertion_ids.add(assertion_id)
            medication = record.get("medication")
            if not isinstance(medication, str) or not medication.strip():
                errors.append(f"{prefix}: medication is required")
            elif medication_names is not None and medication.casefold() not in medication_names:
                errors.append(f"{prefix}: unknown medication {medication!r}")
            if record.get("review_status") != "clinically_approved":
                errors.append(f"{prefix}: release records must be clinically_approved")
            if record.get("evidence_strength") not in EVIDENCE_STRENGTHS:
                errors.append(f"{prefix}: invalid evidence_strength")
            if record.get("source_quality_tier") not in SOURCE_QUALITY_TIERS:
                errors.append(f"{prefix}: invalid source_quality_tier")
            conflict_status = record.get("conflict_status", "not_assessed")
            if conflict_status not in CONFLICT_STATES:
                errors.append(f"{prefix}: invalid conflict_status")
            if conflict_status == "resolved" and not str(record.get("conflict_resolution", "")).strip():
                errors.append(f"{prefix}: resolved conflicts require conflict_resolution")
            if conflict_status not in {"no_known_conflict", "resolved"}:
                errors.append(f"{prefix}: approved release record requires an explicit conflict assessment")
            if record.get("evidence_direction", "unknown") not in {"supports", "contradicts", "qualifies", "unknown"}:
                errors.append(f"{prefix}: invalid evidence_direction")
            if record.get("source_quality_tier") != "not_assessed" and not str(record.get("source_quality_rationale", "")).strip():
                errors.append(f"{prefix}: assessed source quality requires source_quality_rationale")
            if not isinstance(record.get("source"), str) or not record["source"].strip():
                errors.append(f"{prefix}: source is required")
            refs = record.get("evidence_source_ids")
            if not isinstance(refs, list) or not refs:
                errors.append(f"{prefix}: at least one evidence_source_id is required")
            else:
                if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
                    errors.append(f"{prefix}: evidence source IDs must be non-empty strings")
                if len(refs) != len(set(refs)):
                    errors.append(f"{prefix}: duplicate evidence_source_ids")
                if source_ids is not None:
                    for ref in refs:
                        if ref not in source_ids:
                            errors.append(f"{prefix}: unknown evidence source {ref!r}")
            if not isinstance(record.get("jurisdiction"), str) or not record["jurisdiction"].strip():
                errors.append(f"{prefix}: jurisdiction is required")
            if domain == "drug_food_interactions":
                if record.get("severity") not in SEVERITIES:
                    errors.append(f"{prefix}: invalid severity")
                if not isinstance(record.get("food_or_component"), str) or not record["food_or_component"].strip():
                    errors.append(f"{prefix}: food_or_component is required")
                if not isinstance(record.get("clinical_effect"), str) or not record["clinical_effect"].strip():
                    errors.append(f"{prefix}: clinical_effect is required")
            elif domain == "contraindications":
                if not isinstance(record.get("condition_or_population"), str) or not record["condition_or_population"].strip():
                    errors.append(f"{prefix}: condition_or_population is required")
                if not isinstance(record.get("clinical_action"), str) or not record["clinical_action"].strip():
                    errors.append(f"{prefix}: clinical_action is required")
            elif domain == "dosage_references":
                for field in ("indication", "population", "dose_text", "route", "frequency"):
                    if not isinstance(record.get(field), str) or not record[field].strip():
                        errors.append(f"{prefix}: {field} is required")
                if record.get("patient_specific") is not False:
                    errors.append(f"{prefix}: patient_specific must be false; references are not individualized prescriptions")
            elif domain == "administration_instructions":
                if not isinstance(record.get("instruction"), str) or not record["instruction"].strip():
                    errors.append(f"{prefix}: instruction is required")
    return errors


def classify_assertion(record: dict[str, Any]) -> str:
    """Classify governance state without inferring a negative clinical finding."""
    if record.get("conflict_status") == "conflicting_evidence":
        return "conflicting_evidence"
    if record.get("review_status") == "clinically_approved":
        return "assertion_present_reviewed"
    return "assertion_present_unreviewed"


def validate_release_evidence_sources(payload: dict[str, Any]) -> list[str]:
    """Validate provenance and per-source quality appraisal metadata in a release."""
    import re

    errors: list[str] = []
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        return ["evidence_sources: sources must be an array"]
    seen: set[str] = set()
    for index, source in enumerate(payload["sources"]):
        prefix = f"evidence_sources.sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix}: source must be an object")
            continue
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            errors.append(f"{prefix}: source_id is required")
        elif source_id in seen:
            errors.append(f"{prefix}: duplicate source_id {source_id}")
        else:
            seen.add(source_id)
        for digest_field in ("source_response_sha256", "normalized_payload_sha256", "metadata_sha256"):
            if not re.fullmatch(r"[a-f0-9]{64}", str(source.get(digest_field, ""))):
                errors.append(f"{prefix}: {digest_field} must be a SHA-256 digest")
        if source.get("verification_status") != "integrity_verified_clinical_review_recorded":
            errors.append(f"{prefix}: source is not integrity-verified and clinically reviewed")
        appraisals = source.get("source_quality_assessments", [])
        if not isinstance(appraisals, list) or not appraisals:
            errors.append(f"{prefix}: source_quality_assessments must be a non-empty array")
            continue
        if not isinstance(source.get("publisher"), str) or not source["publisher"].strip():
            errors.append(f"{prefix}: publisher is required")
        if not isinstance(source.get("document_title"), str) or not source["document_title"].strip():
            errors.append(f"{prefix}: document_title is required")
        if source.get("source_type") not in SOURCE_TYPES:
            errors.append(f"{prefix}: invalid source_type")
        canonical_url = source.get("canonical_url")
        if not isinstance(canonical_url, str) or not canonical_url.startswith("https://"):
            errors.append(f"{prefix}: canonical_url must be HTTPS")
        for appraisal_index, appraisal in enumerate(appraisals):
            app_prefix = f"{prefix}.source_quality_assessments[{appraisal_index}]"
            if not isinstance(appraisal, dict):
                errors.append(f"{app_prefix}: appraisal must be an object")
                continue
            if not isinstance(appraisal.get("candidate_id"), str) or not appraisal["candidate_id"].strip():
                errors.append(f"{app_prefix}: candidate_id is required")
            if not isinstance(appraisal.get("clinical_decision_id"), str) or not appraisal["clinical_decision_id"].strip():
                errors.append(f"{app_prefix}: clinical_decision_id is required")
            if not isinstance(appraisal.get("clinical_reviewer_id"), str) or not appraisal["clinical_reviewer_id"].strip():
                errors.append(f"{app_prefix}: clinical_reviewer_id is required")
            if appraisal.get("clinical_reviewer_role") not in {"clinical_pharmacist", "physician"}:
                errors.append(f"{app_prefix}: clinical_reviewer_role is not authorized")
            quality = appraisal.get("quality")
            if quality not in SOURCE_QUALITY_TIERS:
                errors.append(f"{app_prefix}: invalid quality value")
            if quality != "not_assessed" and not str(appraisal.get("rationale", "")).strip():
                errors.append(f"{app_prefix}: assessed quality requires rationale")
            if appraisal.get("evidence_direction", "unknown") not in {"supports", "contradicts", "qualifies", "unknown"}:
                errors.append(f"{app_prefix}: invalid evidence_direction")
    return errors
