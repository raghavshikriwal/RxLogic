"""Deterministic DailyMed SPL section-to-domain review previews.

This module performs label-section classification only. It does not interpret
clinical meaning, create curation records, approve evidence, or promote releases.
Unknown/ambiguous sections are deliberately left unmapped.
"""
from __future__ import annotations

import re
from typing import Any

# DailyMed SPL section codes are preferred where known; normalized titles are
# retained as a fallback because SPL publishers do not use perfectly uniform
# titles across every label revision.
_SECTION_MAP: dict[str, tuple[str, str]] = {
    "34067-9": ("approved_indications", "approved_indication"),
    "34068-7": ("dosage_references", "dosage_reference"),
    "34070-3": ("contraindications", "contraindication"),
    "43685-7": ("precautions", "precaution"),
    "34084-4": ("adverse_effects", "adverse_effect"),
}
_TITLE_MAP: dict[str, tuple[str, str]] = {
    "INDICATIONS AND USAGE": ("approved_indications", "approved_indication"),
    "DOSAGE AND ADMINISTRATION": ("dosage_references", "dosage_reference"),
    "CONTRAINDICATIONS": ("contraindications", "contraindication"),
    "WARNINGS AND PRECAUTIONS": ("precautions", "precaution"),
    "WARNINGS": ("precautions", "precaution"),
    "PRECAUTIONS": ("precautions", "precaution"),
    "ADVERSE REACTIONS": ("adverse_effects", "adverse_effect"),
}


def _clean_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()


def preview_dailymed_section_candidates(
    payload: dict[str, Any], canonical_medication: str,
) -> dict[str, Any]:
    """Return locator-preserving, non-authoritative candidate previews.

    The output is intentionally not in the curation store's candidate schema:
    a human must inspect and explicitly author/submit a valid candidate after
    the underlying evidence record has been accepted for curation.
    """
    if not isinstance(payload, dict):
        raise ValueError("DailyMed payload must be an object")
    medication = _clean_text(canonical_medication, 200)
    if not medication:
        raise ValueError("canonical_medication is required")
    sections = payload.get("sections")
    if not isinstance(sections, list):
        raise ValueError("DailyMed payload sections must be an array")

    previews: list[dict[str, Any]] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        title = _clean_text(section.get("section_title"), 300)
        code = _clean_text(section.get("section_code"), 40)
        excerpt = _clean_text(section.get("original_text"), 4000)
        if not title and not excerpt:
            continue
        mapped = _SECTION_MAP.get(code) or _TITLE_MAP.get(_normalize_title(title))
        if mapped:
            domain, candidate_type = mapped
            mapping_status = "mapped_for_human_review"
        else:
            domain, candidate_type = None, None
            mapping_status = "unmapped_human_classification_required"
        previews.append({
            "preview_id": f"dailymed-section-{index + 1}",
            "medication": medication,
            "canonical_domain": domain,
            "candidate_type": candidate_type,
            "mapping_status": mapping_status,
            "source_locator": {
                "source_type": "dailymed_spl",
                "set_id": payload.get("set_id"),
                "spl_version": payload.get("spl_version"),
                "section_code": code or None,
                "section_title": title or None,
            },
            "source_excerpt": excerpt,
            "candidate_completeness": "requires_human_structuring" if mapped else "not_mapped",
            "clinical_interpretation_performed": False,
            "review_status": "pending_clinical_review",
            "promotion_status": "staged_only",
            "curation_record_created": False,
        })
    return {
        "schema": "rxlogic.dailymed_section_preview.v1",
        "medication": medication,
        "set_id": payload.get("set_id"),
        "label_title": payload.get("label_title"),
        "preview_count": len(previews),
        "mapped_count": sum(item["canonical_domain"] is not None for item in previews),
        "unmapped_count": sum(item["canonical_domain"] is None for item in previews),
        "previews": previews,
        "governance": {
            "is_clinical_assertion": False,
            "creates_curation_record": False,
            "requires_human_review": True,
            "can_be_promoted": False,
            "message": "These are source-located extraction previews only. They are not clinical assertions or approved findings.",
        },
    }


def preview_staged_dailymed_evidence(record_id: str, canonical_medication: str, staging_root=None) -> dict[str, Any]:
    """Verify a staged evidence record before creating section previews.

    The preview is read-only and available for review preparation regardless of
    the current review decision. It never changes the decision ledger.
    """
    from services.evidence_review import DEFAULT_STAGING_ROOT, EvidenceReviewError, inspect_evidence

    root = staging_root or DEFAULT_STAGING_ROOT
    try:
        inspected = inspect_evidence(record_id, root)
    except EvidenceReviewError:
        raise
    metadata = inspected.get("metadata", {})
    payload = inspected.get("payload")
    if metadata.get("source_type") != "dailymed_spl":
        raise ValueError("Evidence record is not a DailyMed SPL document")
    if not isinstance(payload, dict) or payload.get("schema") != "rxlogic.dailymed_spl_candidate.v1":
        raise ValueError("Evidence record does not contain a supported DailyMed SPL payload")
    result = preview_dailymed_section_candidates(payload, canonical_medication)
    result["evidence"] = {
        "record_id": inspected["record"].get("record_id"),
        "review_status": inspected["record"].get("review_status"),
        "promotion_status": "staged_only",
        "metadata_integrity": inspected.get("metadata_integrity"),
        "source_response_sha256": inspected.get("source_response_sha256"),
        "normalized_payload_sha256": inspected.get("normalized_payload_sha256"),
        "canonical_url": metadata.get("canonical_url"),
        "jurisdiction": metadata.get("jurisdiction"),
        "publisher": metadata.get("publisher"),
    }
    return result
