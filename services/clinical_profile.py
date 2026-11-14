"""Read-only, evidence-traceable clinical profile for one catalog medication.

This module only *presents* governed knowledge. It never authors, approves,
infers or fills in a clinical statement:

* Approved findings come exclusively from an integrity-verified active release
  (``RXLOGIC_KNOWLEDGE_MODE=active_release``) and must pass
  ``is_release_usable`` (explicit clinical approval + explicit conflict state +
  at least one evidence source).
* In ``legacy_development`` mode the mutable development files are never an
  authority: records found there are reported only as counts/IDs with their
  review state, never as findings, and their text is withheld.
* A domain with no approved finding is reported as missing evidence. An empty
  domain is "not assessed", never "no risk".
* Dosage references are returned as source-scoped references and are always
  flagged ``patient_specific: false``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from services.clinical_knowledge import (
    ALL_DOMAINS, DOMAINS, EXTENDED_DOMAINS, is_release_usable,
)
from services.knowledge_release import DEFAULT_KNOWLEDGE_ROOT, load_active_release

SCHEMA_VERSION = "1.0.0"
DISCLAIMER = (
    "Educational demonstrator only. Not for diagnosis, prescribing, dose selection or "
    "independent medication changes. Clinical use is not permitted."
)

DOMAIN_LABELS: dict[str, str] = {
    "medication_overviews": "Medication overview",
    "drug_classes": "Drug class",
    "therapeutic_categories": "Therapeutic category",
    "mechanisms_of_action": "Mechanism of action",
    "approved_indications": "Approved indications",
    "administration_instructions": "Administration information",
    "contraindications": "Contraindications",
    "precautions": "Precautions",
    "adverse_effects": "Adverse effects",
    "dosage_references": "Dosage references",
    "drug_food_interactions": "Drug–food interactions",
    "drug_supplement_interactions": "Drug–supplement interactions",
}
# Presentation order: identity first, then use, safety, interactions.
DOMAIN_ORDER: tuple[str, ...] = tuple(DOMAIN_LABELS)
_STATEMENT_FIELD = {
    "contraindications": ("condition_or_population", "clinical_action"),
    "drug_food_interactions": ("food_or_component", "clinical_effect"),
    "drug_supplement_interactions": ("supplement_or_component", "clinical_effect"),
    "administration_instructions": (None, "instruction"),
    "dosage_references": (None, "dose_text"),
}
SOURCE_FIELDS = (
    "source_id", "publisher", "source_type", "document_title", "document_version",
    "publication_date", "retrieved_at", "jurisdiction", "canonical_url", "locator",
    "verification_status",
)


class UnknownMedicationLookup(LookupError):
    """Raised when a name is not a catalog canonical name or alias."""

    def __init__(self, name: str):
        super().__init__(f"unknown medication: {name!r}")
        self.name = name


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {Path(path).name}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{Path(path).name} must contain a JSON object")
    return value


class KnowledgeView:
    """The datasets needed to build profiles, plus how much to trust them."""

    def __init__(self, *, mode: str, release: str, catalog: dict[str, Any],
                 assertions: dict[str, Any], interaction_rules: list[dict[str, Any]],
                 sources: dict[str, dict[str, Any]], authoritative: bool):
        self.mode = mode
        self.release = release
        self.catalog = catalog
        self.assertions = assertions
        self.interaction_rules = interaction_rules
        self.sources = sources
        # Only a verified active release may present records as approved.
        self.authoritative = authoritative
        self._terms: dict[str, str] = {}
        for row in catalog.get("medications", []):
            canonical = str(row["canonical_name"]).casefold()
            self._terms[canonical] = canonical
            for alias in row.get("aliases", []):
                self._terms[str(alias).casefold()] = canonical
        self._rows = {str(r["canonical_name"]).casefold(): r for r in catalog.get("medications", [])}

    @classmethod
    def load(cls, root: Path | None = None, mode: str | None = None) -> "KnowledgeView":
        root = Path(root) if root else DEFAULT_KNOWLEDGE_ROOT
        mode = (mode or os.getenv("RXLOGIC_KNOWLEDGE_MODE", "legacy_development")).strip().lower()
        if mode == "active_release":
            bundle = load_active_release(root)  # raises KnowledgeReleaseError: fail closed
            catalog = bundle.get("medication_catalog") or _read_json(root / "medication_catalog.json")
            return cls(
                mode=mode, release=bundle["manifest"]["knowledge_release"], catalog=catalog,
                assertions=bundle.get("clinical_assertions") or {},
                interaction_rules=list(bundle["interaction_rules"].get("interaction_rules", [])),
                sources={str(s["source_id"]): s for s in bundle["evidence_sources"].get("sources", []) if s.get("source_id")},
                authoritative=True,
            )
        if mode != "legacy_development":
            raise ValueError("RXLOGIC_KNOWLEDGE_MODE must be 'legacy_development' or 'active_release'")
        assertions_path = root / "clinical_assertions.json"
        interactions = _read_json(root / "interaction_rules.json")
        evidence = _read_json(root / "evidence_sources.json")
        return cls(
            mode=mode, release=str(interactions.get("knowledge_release", "unknown")),
            catalog=_read_json(root / "medication_catalog.json"),
            assertions=_read_json(assertions_path) if assertions_path.exists() else {},
            interaction_rules=list(interactions.get("interaction_rules", [])),
            sources={str(s["source_id"]): s for s in evidence.get("sources", []) if s.get("source_id")},
            authoritative=False,
        )

    # -- identity -----------------------------------------------------------

    def resolve(self, name: str) -> str:
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            raise UnknownMedicationLookup(str(name)[:120])
        canonical = self._terms.get(name.strip().casefold())
        if canonical is None:
            raise UnknownMedicationLookup(name.strip())
        return canonical

    def canonical_of(self, name: Any) -> str | None:
        """Canonical catalog name for a name or alias, or None (never raises)."""
        return self._terms.get(str(name).strip().casefold()) if isinstance(name, str) else None

    def identity(self, canonical: str) -> dict[str, Any]:
        row = self._rows[canonical]
        return {
            "canonical_name": canonical,
            "rxcui": str(row.get("rxcui", "")),
            "aliases": list(row.get("aliases", [])),
            "identity_reference": row.get("identity_reference"),
            "identity_status": row.get("identity_status"),
            "clinical_coverage_status": row.get("clinical_coverage_status"),
        }

    def canonical_names(self) -> list[str]:
        return sorted(self._rows)


def _source_refs(view: KnowledgeView, ids: list[str]) -> list[dict[str, Any]]:
    refs = []
    for source_id in ids:
        source = view.sources.get(source_id, {})
        ref = {field: source.get(field) for field in SOURCE_FIELDS}
        ref["source_id"] = source_id
        ref["resolved"] = bool(source)
        refs.append(ref)
    return refs


def _exclusion_reason(record: dict[str, Any], authoritative: bool) -> str:
    """Why a record is not shown as an approved finding (never the record's claim text)."""
    if not authoritative:
        return "development_record_not_an_approval_authority"
    review = record.get("review_status")
    if review in {"rejected", "withdrawn"}:
        return f"review_{review}"
    if review != "clinically_approved":
        return "awaiting_clinical_approval"
    ids = record.get("evidence_source_ids")
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i.strip() for i in ids):
        return "no_evidence_source"
    if record.get("conflict_status") == "resolved" and not str(record.get("conflict_resolution", "")).strip():
        return "conflict_resolution_missing"
    return "conflict_assessment_missing"


def _statement(domain: str, record: dict[str, Any]) -> tuple[str | None, str]:
    """Return (subject, statement text) for a released record of a domain."""
    if domain in _STATEMENT_FIELD:
        subject_field, text_field = _STATEMENT_FIELD[domain]
        return (str(record.get(subject_field)) if subject_field else None), str(record.get(text_field, ""))
    return None, str(record.get("statement", ""))


def _approved_finding(view: KnowledgeView, domain: str, record: dict[str, Any]) -> dict[str, Any]:
    subject, text = _statement(domain, record)
    ids = list(record.get("evidence_source_ids", []))
    finding: dict[str, Any] = {
        "assertion_id": str(record.get("assertion_id", "")),
        "medication": str(record.get("medication", "")),
        "domain": domain,
        "subject": subject,
        "statement": text,
        "evidence_source_ids": ids,
        "sources": _source_refs(view, ids),
        "all_sources_resolved": all(ref["resolved"] for ref in _source_refs(view, ids)),
        "source": str(record.get("source", "")),
        "source_locator": record.get("source_locator"),
        "evidence_strength": record.get("evidence_strength", "unknown"),
        "source_quality_tier": record.get("source_quality_tier", "not_assessed"),
        "severity": record.get("severity"),
        "applicability": {
            "jurisdiction": record.get("jurisdiction", "unspecified"),
            "notes": str(record.get("applicability_notes", "")),
        },
        "review_status": "clinically_approved",
        "conflict_status": record.get("conflict_status"),
        "conflict_resolution": str(record.get("conflict_resolution", "")),
        "is_patient_specific_recommendation": False,
    }
    if domain == "dosage_references":
        finding["dosage_reference"] = {
            field: record.get(field) for field in ("indication", "population", "dose_text", "route", "frequency")
        }
        finding["dosage_reference"]["patient_specific"] = False
    return finding


def _domain_summary(view: KnowledgeView, domain: str, canonical: str) -> dict[str, Any]:
    records = [
        r for r in view.assertions.get(domain, []) or []
        if isinstance(r, dict) and view.canonical_of(r.get("medication")) == canonical
    ]
    approved, pending, conflicts = [], [], []
    for record in records:
        # Legacy/development data is never an approval authority.
        if view.authoritative and is_release_usable(record):
            approved.append(_approved_finding(view, domain, record))
            continue
        recorded_review = str(record.get("review_status", "needs_clinical_review"))
        entry = {
            "assertion_id": str(record.get("assertion_id", "")),
            # A development record is never an approval authority, even if it claims approval.
            "review_status": recorded_review if view.authoritative else "unverified_development_record",
            "recorded_review_status": recorded_review,
            "conflict_status": str(record.get("conflict_status", "not_assessed")),
            "evidence_source_ids": list(record.get("evidence_source_ids", [])),
            "exclusion_reason": _exclusion_reason(record, view.authoritative),
        }
        if record.get("conflict_status") == "conflicting_evidence":
            conflicts.append({**entry, "sources": _source_refs(view, entry["evidence_source_ids"])})
        else:
            pending.append(entry)
    if approved:
        status = "approved_findings"
    elif conflicts:
        status = "conflicting_evidence"
    elif pending:
        status = "awaiting_approval"
    else:
        status = "not_assessed"
    missing = []
    if not approved:
        missing.append("No clinically approved assertion is available for this domain.")
    if domain == "dosage_references" and approved:
        missing.append("Dosage entries are source-scoped references, not patient-specific doses.")
    return {
        "domain": domain,
        "label": DOMAIN_LABELS[domain],
        "status": status,
        "counts": {"approved": len(approved), "awaiting_approval": len(pending), "conflicting": len(conflicts)},
        "findings": approved,
        "awaiting_approval": pending,   # IDs and states only; claim text is withheld
        "conflicting_evidence": conflicts,
        "missing_evidence": missing,
    }


def _interaction_section(view: KnowledgeView, canonical: str) -> dict[str, Any]:
    approved, pending, conflicts = [], [], []
    for rule in view.interaction_rules:
        pair = (view.canonical_of(rule.get("medication_a")) or str(rule.get("medication_a", "")).casefold(),
                view.canonical_of(rule.get("medication_b")) or str(rule.get("medication_b", "")).casefold())
        if canonical not in pair:
            continue
        partner = pair[1] if pair[0] == canonical else pair[0]
        ids = list(rule.get("evidence_source_ids", []))
        recorded_review = str(rule.get("review_status", "needs_clinical_review"))
        base = {
            "rule_id": rule.get("rule_id"), "partner": partner,
            "review_status": recorded_review if view.authoritative else "unverified_development_record",
            "recorded_review_status": recorded_review,
            "conflict_status": str(rule.get("conflict_status", "not_assessed")),
            "evidence_source_ids": ids,
        }
        # Only explicit independent clinical approval counts. The legacy "reviewed"
        # state is a development-file label, not clinical approval.
        has_sources = bool(ids) and all(isinstance(i, str) and i.strip() for i in ids)
        if rule.get("conflict_status") == "conflicting_evidence":
            conflicts.append({**base, "sources": _source_refs(view, ids)})
        elif view.authoritative and recorded_review == "clinically_approved" and has_sources:
            approved.append({
                **base, "severity": rule.get("severity", "unknown"),
                "evidence_strength": rule.get("evidence_strength", rule.get("evidence", "unknown")),
                "statement": str(rule.get("description", "")),
                "source": str(rule.get("source", "")), "sources": _source_refs(view, ids),
                "all_sources_resolved": all(ref["resolved"] for ref in _source_refs(view, ids)),
                "source_locator": rule.get("source_locator"),
                "jurisdiction": rule.get("jurisdiction", "unspecified"),
            })
        else:
            pending.append({**base, "exclusion_reason": _exclusion_reason(rule, view.authoritative)})  # no claim text
    if approved:
        status = "approved_findings"
    elif conflicts:
        status = "conflicting_evidence"
    elif pending:
        status = "awaiting_approval"
    else:
        status = "not_assessed"
    return {
        "domain": "drug_drug_interactions", "label": "Drug–drug interactions", "status": status,
        "counts": {"approved": len(approved), "awaiting_approval": len(pending), "conflicting": len(conflicts)},
        "findings": approved, "awaiting_approval": sorted(pending, key=lambda r: r["partner"]),
        "conflicting_evidence": sorted(conflicts, key=lambda r: r["partner"]),
        "missing_evidence": [] if approved else ["No clinically approved interaction rule is available."],
    }


def build_medication_profile(view: KnowledgeView, name: str) -> dict[str, Any]:
    """Build the full profile for one medication (canonical name or alias)."""
    canonical = view.resolve(name)
    domains = {d: _domain_summary(view, d, canonical) for d in DOMAIN_ORDER}
    interactions = _interaction_section(view, canonical)
    sections = [*domains.values(), interactions]
    with_approved = sum(s["counts"]["approved"] > 0 for s in sections)
    if with_approved == 0:
        assessment = "not_assessed"
    elif with_approved < len(sections):
        assessment = "partial"
    else:
        assessment = "approved_findings_in_every_section"
    return {
        "schema_version": SCHEMA_VERSION,
        "medication": view.identity(canonical),
        "knowledge": {
            "mode": view.mode, "release": view.release,
            "approved_content_is_authoritative": view.authoritative,
            "clinical_use_permitted": False,
        },
        "assessment_state": assessment,
        "sections_with_approved_findings": with_approved,
        "section_count": len(sections),
        "domains": domains,
        "drug_drug_interactions": interactions,
        "interpretation": (
            "Empty or missing sections mean not assessed, never absence of risk. "
            "Only clinically approved assertions from a verified knowledge release are shown as findings."
        ),
        "disclaimer": DISCLAIMER,
    }


def build_catalog_overview(view: KnowledgeView) -> dict[str, Any]:
    """Light-weight listing of every catalog identity with coverage counts."""
    medications = []
    for canonical in view.canonical_names():
        profile = build_medication_profile(view, canonical)
        medications.append({
            **profile["medication"],
            "assessment_state": profile["assessment_state"],
            "sections_with_approved_findings": profile["sections_with_approved_findings"],
            "section_count": profile["section_count"],
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "knowledge": {"mode": view.mode, "release": view.release,
                      "approved_content_is_authoritative": view.authoritative,
                      "clinical_use_permitted": False},
        "medication_count": len(medications),
        "medications": medications,
        "disclaimer": DISCLAIMER,
    }


__all__ = [
    "ALL_DOMAINS", "DOMAINS", "EXTENDED_DOMAINS", "DOMAIN_LABELS", "DOMAIN_ORDER",
    "KnowledgeView", "UnknownMedicationLookup", "build_catalog_overview", "build_medication_profile",
]
