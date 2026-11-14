"""Draft candidate rule files from an ingested openFDA drug-label snapshot.

This is an *authoring aid*, not a knowledge source and not an approver:

* Statements are copied verbatim from the source (whitespace collapsed only);
  nothing is summarised, paraphrased or generated.
* ``evidence_strength`` is always ``unknown``, ``source_quality_tier`` is
  ``not_assessed`` and ``conflict_status`` is ``not_assessed``. A human author
  must appraise them before the candidate can be approved.
* Drafts are plain rule files for ``scripts.manage_knowledge candidate-create``.
  That command still requires accepted, hash-verified evidence, a named human
  author, and an independent clinical approver. Drafting never writes to any
  runtime dataset or review ledger.
* Sections that need clinical structuring (contraindications, dosage,
  administration) are emitted as incomplete drafts that carry the verbatim
  excerpt and a list of fields the author must supply; they fail candidate
  validation until completed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATEMENT_LIMIT = 2000
EXCERPT_LIMIT = 4000

# openFDA label field -> (candidate type, completeness)
#   "statement": the verbatim text is itself a complete candidate statement.
#   "structured": an author must derive structured fields from the excerpt.
SECTION_MAP: dict[str, tuple[str, str]] = {
    "indications_and_usage": ("approved_indication", "statement"),
    "mechanism_of_action": ("mechanism_of_action", "statement"),
    "precautions": ("precaution", "statement"),
    "warnings_and_cautions": ("precaution", "statement"),
    "adverse_reactions": ("adverse_effect", "statement"),
    "contraindications": ("contraindication", "structured"),
    "dosage_and_administration": ("dosage_reference", "structured"),
}
# Fields an author must supply for structured drafts (see candidate schema).
STRUCTURED_FIELDS: dict[str, tuple[str, ...]] = {
    "contraindication": ("condition_or_population", "clinical_action", "evidence_strength"),
    "dosage_reference": ("indication", "population", "dose_text", "route", "frequency", "evidence_strength"),
}
# Sections listed for manual review only: pairing/structuring is not mechanical.
MANUAL_REVIEW_SECTIONS = ("drug_interactions", "food_interactions", "drug_and_or_laboratory_test_interactions")


class LabelDraftingError(ValueError):
    """Raised when a label payload cannot be drafted safely."""


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _label_identity(label: dict[str, Any]) -> set[str]:
    openfda = label.get("openfda") if isinstance(label.get("openfda"), dict) else {}
    names: set[str] = set()
    for field in ("generic_name", "substance_name"):
        for value in openfda.get(field, []) or []:
            if isinstance(value, str):
                names.add(value.casefold())
    return names


def _matches_medication(label: dict[str, Any], terms: set[str]) -> bool:
    return any(term in name for name in _label_identity(label) for term in terms)


def _first_label(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise LabelDraftingError("payload is not an openFDA label response with a 'results' array")
    return [row for row in payload["results"] if isinstance(row, dict)]


def draft_from_openfda_label(
    payload: Any, metadata: dict[str, Any], medication: str, aliases: list[str] | None = None,
) -> dict[str, Any]:
    """Return ``{"drafts": [...], "skipped": [...], "manual_review_sections": [...]}``."""
    medication = medication.strip().casefold()
    if not medication:
        raise LabelDraftingError("medication is required")
    terms = {medication, *(a.casefold() for a in (aliases or []))}
    labels = _first_label(payload)
    matching = [(i, row) for i, row in enumerate(labels) if _matches_medication(row, terms)]
    if not matching:
        raise LabelDraftingError(
            f"no label in this evidence identifies {medication!r}; refusing to draft for a different product"
        )
    publisher = str(metadata.get("publisher", "")).strip()
    title = str(metadata.get("document_title", metadata.get("title", ""))).strip()
    jurisdiction = str(metadata.get("jurisdiction") or "unspecified").strip() or "unspecified"
    drafts: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    manual: list[str] = []

    for label_index, label in matching:
        version = label.get("version", "unknown")
        locator_base = (
            f"openFDA drug label results[{label_index}]; set_id={label.get('set_id', 'unknown')}; "
            f"version={version}; effective_time={label.get('effective_time', 'unknown')}"
        )
        source = f"{publisher}: {title}".strip(": ")[:1000] or "openFDA drug label"
        common = {
            "medication": medication, "source": source, "jurisdiction": jurisdiction,
            "evidence_strength": "unknown", "source_quality_tier": "not_assessed",
            "conflict_status": "not_assessed", "evidence_direction": "unknown",
            "applicability_notes": "Drafted from the product label; confirm formulation, population and indication scope.",
        }
        for field, (candidate_type, completeness) in SECTION_MAP.items():
            values = label.get(field)
            if not isinstance(values, list):
                continue
            for j, value in enumerate(values):
                if not isinstance(value, str) or not value.strip():
                    continue
                text = _collapse(value)
                locator = f"{locator_base}; field={field}[{j}]"
                rule = {**common, "source_locator": locator}
                missing: list[str] = []
                if completeness == "statement":
                    if len(text) > STATEMENT_LIMIT:
                        skipped.append({"field": field, "locator": locator,
                                        "reason": f"section is {len(text)} characters; author must select a passage (limit {STATEMENT_LIMIT})"})
                        continue
                    rule["statement"] = text
                else:
                    if len(text) > EXCERPT_LIMIT:
                        skipped.append({"field": field, "locator": locator,
                                        "reason": f"section is {len(text)} characters; author must select a passage (limit {EXCERPT_LIMIT})"})
                        continue
                    rule["source_excerpt"] = text
                    rule.pop("evidence_strength", None)  # must be a deliberate author choice here
                    missing = [f for f in STRUCTURED_FIELDS[candidate_type] if f not in rule]
                drafts.append({
                    "candidate_type": candidate_type,
                    "draft_status": "ready_for_author_review" if not missing else "needs_author_completion",
                    "missing_required_fields": missing,
                    "section": field,
                    "source_locator": locator,
                    "rule": rule,
                })
        # Pharmacologic class labels are carried as structured openFDA fields.
        openfda = label.get("openfda") if isinstance(label.get("openfda"), dict) else {}
        for field in ("pharm_class_epc", "pharm_class_moa"):
            for j, value in enumerate(openfda.get(field, []) or []):
                if isinstance(value, str) and value.strip():
                    candidate_type = "drug_class" if field == "pharm_class_epc" else "mechanism_of_action"
                    drafts.append({
                        "candidate_type": candidate_type,
                        "draft_status": "ready_for_author_review",
                        "missing_required_fields": [],
                        "section": f"openfda.{field}",
                        "source_locator": f"{locator_base}; field=openfda.{field}[{j}]",
                        "rule": {**common, "statement": _collapse(value),
                                 "source_locator": f"{locator_base}; field=openfda.{field}[{j}]"},
                    })
        manual.extend(f for f in MANUAL_REVIEW_SECTIONS if isinstance(label.get(f), list) and label.get(f))
    return {
        "medication": medication,
        "draft_count": len(drafts),
        "drafts": drafts,
        "skipped": skipped,
        "manual_review_sections": sorted(set(manual)),
        "notice": "Drafts are not candidates, not reviewed and not approved. Appraise evidence strength and conflicts before authoring.",
    }


def write_drafts(result: dict[str, Any], out_dir: Path) -> list[Path]:
    """Write one ``.rule.json`` per draft plus an ``index.json``; never overwrites."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    index = []
    for number, draft in enumerate(result["drafts"], 1):
        path = out / f"{result['medication'].replace(' ', '-')}-{number:03d}-{draft['candidate_type']}.rule.json"
        if path.exists():
            raise LabelDraftingError(f"refusing to overwrite existing draft: {path.name}")
        path.write_text(json.dumps(draft["rule"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
        index.append({"file": path.name, **{k: draft[k] for k in ("candidate_type", "draft_status", "missing_required_fields", "section", "source_locator")}})
    index_path = out / f"{result['medication'].replace(' ', '-')}-index.json"
    if index_path.exists():
        raise LabelDraftingError(f"refusing to overwrite existing index: {index_path.name}")
    index_path.write_text(json.dumps({
        "medication": result["medication"], "drafts": index, "skipped": result["skipped"],
        "manual_review_sections": result["manual_review_sections"], "notice": result["notice"],
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    written.append(index_path)
    return written
