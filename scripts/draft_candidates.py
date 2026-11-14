"""Draft candidate rule files from an ingested openFDA label (authoring aid only).

Usage (from the repository root):

    python -m scripts.draft_candidates --evidence-id EVD-... --medication metformin --out-dir .\\drafts

Output files are inputs for ``scripts.manage_knowledge candidate-create``. This
command never creates candidates, approvals or releases.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from services.evidence_review import DEFAULT_STAGING_ROOT, EvidenceReviewError, inspect_evidence
from services.label_drafting import LabelDraftingError, draft_from_openfda_label, write_drafts
from services.medication_catalog import MedicationCatalogError, load_medication_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence-id", required=True, help="Staged evidence record ID (EVD-...)")
    parser.add_argument("--medication", required=True, help="Catalog canonical name or alias")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--staging-dir", type=Path, default=DEFAULT_STAGING_ROOT)
    args = parser.parse_args(argv)
    try:
        catalog = load_medication_catalog()
        wanted = args.medication.strip().casefold()
        row = next((r for r in catalog["medications"]
                    if wanted == r["canonical_name"] or wanted in r.get("aliases", [])), None)
        if row is None:
            raise LabelDraftingError(f"{args.medication!r} is not in the medication catalog")
        evidence = inspect_evidence(args.evidence_id, args.staging_dir)
        result = draft_from_openfda_label(
            evidence["payload"], evidence["metadata"], row["canonical_name"], row.get("aliases", []),
        )
        written = write_drafts(result, args.out_dir)
    except (LabelDraftingError, EvidenceReviewError, MedicationCatalogError, OSError) as exc:
        print(f"draft failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "medication": result["medication"], "draft_count": result["draft_count"],
        "skipped": len(result["skipped"]), "manual_review_sections": result["manual_review_sections"],
        "files": [p.name for p in written], "notice": result["notice"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
