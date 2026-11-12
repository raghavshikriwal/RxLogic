"""Command-line interface for reviewing staged evidence (no rule promotion)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.evidence_ingestion import DEFAULT_STAGING_ROOT
from services.evidence_review import (
    VALID_DECISIONS,
    EvidenceReviewError,
    inspect_evidence,
    list_review_queue,
    record_review_decision,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    queue = commands.add_parser("queue", help="List evidence awaiting review")
    queue.add_argument("--status", default="pending_clinical_review", choices=["pending_clinical_review", "accepted_for_curation", "rejected", "request_more_evidence", "all"])
    show = commands.add_parser("show", help="Inspect one evidence record")
    show.add_argument("record_id")
    decide = commands.add_parser("decide", help="Append an auditable review decision")
    decide.add_argument("record_id")
    decide.add_argument("decision", choices=sorted(VALID_DECISIONS))
    decide.add_argument("--reviewer-id", required=True)
    decide.add_argument("--reviewer-role", required=True)
    decide.add_argument("--rationale", required=True)
    decide.add_argument("--request-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "queue":
            result = list_review_queue(args.staging_root, args.status)
        elif args.command == "show":
            result = inspect_evidence(args.record_id, args.staging_root)
        else:
            result = record_review_decision(
                args.record_id, args.decision, args.reviewer_id,
                args.reviewer_role, args.rationale, args.staging_root,
                args.request_id,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except EvidenceReviewError as exc:
        print(f"Review error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
