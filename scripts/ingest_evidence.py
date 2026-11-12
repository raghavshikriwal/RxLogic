"""Stage a locally downloaded official-source JSON document for clinical review.

Example:
    python -m scripts.ingest_evidence --input label.json --publisher openFDA \\
      --source-type fda_label --title "Example drug label" \\
      --url "https://api.fda.gov/drug/label.json?search=..." 
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.evidence_ingestion import EvidenceMetadata, ingest_json_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Path to a UTF-8 JSON source snapshot")
    parser.add_argument("--publisher", required=True, help="Publishing organization")
    parser.add_argument(
        "--source-type",
        required=True,
        choices=("fda_label", "rxnorm_concept", "dailymed_spl", "clinical_guideline", "systematic_review", "regulatory_notice", "other"),
    )
    parser.add_argument("--title", required=True, help="Document or dataset title")
    parser.add_argument("--url", required=True, help="Canonical HTTPS URL on an approved source domain")
    parser.add_argument("--publication-date", help="Publication date (YYYY-MM-DD)")
    parser.add_argument("--jurisdiction", help="Applicable jurisdiction, if known")
    parser.add_argument(
        "--staging-dir",
        type=Path,
        help="Optional staging directory (defaults to knowledge/ingestion/staging)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    metadata = EvidenceMetadata(
        publisher=args.publisher,
        source_type=args.source_type,
        document_title=args.title,
        canonical_url=args.url,
        publication_date=args.publication_date,
        jurisdiction=args.jurisdiction,
    )
    try:
        kwargs = {"staging_root": args.staging_dir} if args.staging_dir else {}
        result = ingest_json_document(args.input, metadata, **kwargs)
    except (ValueError, OSError) as exc:
        print(f"Ingestion rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "record_id": result.record_id,
        "source_id": result.source_id,
        "content_sha256": result.content_sha256,
        "artifact_path": result.artifact_path,
        "duplicate": result.duplicate,
        "review_status": result.review_status,
        "promotion_status": result.promotion_status,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
