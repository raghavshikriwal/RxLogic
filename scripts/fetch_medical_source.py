"""Fetch a bounded official-source JSON snapshot and stage it for review.

Examples:
  python -m scripts.fetch_medical_source rxnorm metformin
  python -m scripts.fetch_medical_source openfda metformin --limit 5
  python -m scripts.fetch_medical_source dailymed metformin --page-size 10
"""
from __future__ import annotations

import argparse
import json

from models.exceptions import ExternalAPIError
from services.medical_source_client import MedicalSourceClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("rxnorm", "openfda", "dailymed"))
    parser.add_argument("medication_name")
    parser.add_argument("--limit", type=int, default=5, help="openFDA result count (1-100)")
    parser.add_argument("--page-size", type=int, default=10, help="DailyMed page size (1-100)")
    parser.add_argument("--staging-dir", help="Optional evidence staging directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from pathlib import Path

    client = MedicalSourceClient(
        staging_root=Path(args.staging_dir) if args.staging_dir else None
    )
    try:
        if args.provider == "rxnorm":
            result = client.fetch_and_stage_rxnorm_concept(args.medication_name)
        elif args.provider == "openfda":
            result = client.fetch_and_stage_openfda_label(args.medication_name, args.limit)
        else:
            result = client.fetch_and_stage_dailymed_labels(args.medication_name, args.page_size)
    except (ValueError, OSError, ExternalAPIError) as exc:
        print(f"Source fetch/staging failed: {exc}")
        return 2

    print(json.dumps({
        "provider": result.provider,
        "query": result.query,
        "source_url": result.source_url,
        "result_count": result.result_count,
        "record_id": result.ingestion.record_id,
        "content_sha256": result.ingestion.content_sha256,
        "artifact_path": result.ingestion.artifact_path,
        "duplicate": result.ingestion.duplicate,
        "review_status": result.ingestion.review_status,
        "promotion_status": result.ingestion.promotion_status,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
