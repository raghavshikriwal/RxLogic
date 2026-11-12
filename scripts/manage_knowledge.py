"""Controlled knowledge release management CLI.

This CLI records governance actor IDs and roles for auditability. It is not an
identity provider: deployments must restrict shell access to authorized staff.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.evidence_ingestion import DEFAULT_STAGING_ROOT
from services.knowledge_curation import DEFAULT_CURATION_ROOT, list_candidates, create_candidate, record_clinical_decision
from services.knowledge_release import (
    DEFAULT_KNOWLEDGE_ROOT,
    KnowledgeReleaseError,
    create_release,
    inspect_release,
    list_releases,
    load_active_release,
    promote_release,
    rollback_release,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--knowledge-root", type=Path, default=DEFAULT_KNOWLEDGE_ROOT)
    parser.add_argument("--curation-root", type=Path, default=DEFAULT_CURATION_ROOT)
    parser.add_argument("--staging-root", type=Path, default=DEFAULT_STAGING_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("candidates", help="List curated candidates and their approval state")
    candidate_create = commands.add_parser("candidate-create", help="Create an evidence-backed clinical knowledge candidate")
    candidate_create.add_argument("--type", required=True, choices=["interaction_rule", "food_rule", "drug_food_interaction", "contraindication", "dosage_reference", "administration_instruction"])
    candidate_create.add_argument("--rule-file", required=True, type=Path, help="UTF-8 JSON file containing the candidate assertion")
    candidate_create.add_argument("--evidence-id", required=True, action="append", help="Accepted evidence record ID; repeat for multiple sources")
    candidate_create.add_argument("--author-id", required=True)
    candidate_create.add_argument("--rationale", required=True)
    candidate_decide = commands.add_parser("candidate-decide", help="Record independent clinical review of a candidate")
    candidate_decide.add_argument("candidate_id")
    candidate_decide.add_argument("--decision", required=True, choices=["approved", "rejected", "request_changes"])
    candidate_decide.add_argument("--reviewer-id", required=True)
    candidate_decide.add_argument("--reviewer-role", required=True, choices=["clinical_pharmacist", "physician"])
    candidate_decide.add_argument("--rationale", required=True)
    commands.add_parser("releases", help="List release bundles and integrity status")
    commands.add_parser("status", help="Show the active release; fail closed if none is active")
    create = commands.add_parser("create", help="Build an immutable release (does not activate it)")
    create.add_argument("candidate_ids", nargs="+", help="One or more candidate IDs")
    create.add_argument("--actor-id", required=True)
    create.add_argument("--rationale", required=True)
    promote = commands.add_parser("promote", help="Explicitly activate an immutable release")
    promote.add_argument("release_id")
    promote.add_argument("--actor-id", required=True)
    promote.add_argument("--actor-role", required=True, choices=["knowledge_steward", "administrator"])
    rollback = commands.add_parser("rollback", help="Restore a previously promoted release")
    rollback.add_argument("release_id")
    rollback.add_argument("--actor-id", required=True)
    rollback.add_argument("--actor-role", required=True, choices=["knowledge_steward", "administrator"])
    inspect = commands.add_parser("inspect", help="Inspect and verify one immutable release")
    inspect.add_argument("release_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "candidates":
            result = list_candidates(args.curation_root)
        elif args.command == "candidate-create":
            try:
                rule = json.loads(args.rule_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Cannot read candidate rule JSON: {exc}") from exc
            result = create_candidate(args.type, rule, args.evidence_id, args.author_id, args.rationale,
                                      args.staging_root, args.curation_root)
        elif args.command == "candidate-decide":
            result = record_clinical_decision(args.candidate_id, args.decision, args.reviewer_id,
                                              args.reviewer_role, args.rationale,
                                              args.curation_root, args.staging_root)
        elif args.command == "releases":
            result = list_releases(args.knowledge_root)
        elif args.command == "status":
            bundle = load_active_release(args.knowledge_root)
            result = {"active": True, "knowledge_release": bundle["manifest"]["knowledge_release"],
                      "created_at": bundle["manifest"]["created_at"], "clinical_use_permitted": False}
        elif args.command == "create":
            result = create_release(args.candidate_ids, args.actor_id, args.rationale,
                                    args.curation_root, args.staging_root, args.knowledge_root)
        elif args.command == "promote":
            result = promote_release(args.release_id, args.actor_id, args.actor_role,
                                     args.knowledge_root, args.curation_root, args.staging_root)
        elif args.command == "rollback":
            result = rollback_release(args.release_id, args.actor_id, args.actor_role, args.knowledge_root)
        else:
            result = inspect_release(args.release_id, args.knowledge_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (KnowledgeReleaseError, OSError, ValueError) as exc:
        print(f"Knowledge management error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
