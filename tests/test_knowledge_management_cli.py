from __future__ import annotations

import json
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.manage_knowledge import main


def test_cli_lists_candidates_and_releases(tmp_path, capsys):
    knowledge = tmp_path / "knowledge"
    curation = tmp_path / "curation"
    curation.mkdir()
    (curation / "candidates.jsonl").write_text("", encoding="utf-8")

    assert main(["--knowledge-root", str(knowledge), "--curation-root", str(curation), "candidates"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert main(["--knowledge-root", str(knowledge), "releases"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_cli_status_fails_closed_without_active_release(tmp_path, capsys):
    assert main(["--knowledge-root", str(tmp_path), "status"]) == 2
    assert "no active approved knowledge release" in capsys.readouterr().out


def test_cli_rejects_unauthorized_promotion_role(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["--knowledge-root", str(tmp_path), "promote", "RXK-20261113T010101Z-ABCDEF12",
              "--actor-id", "someone", "--actor-role", "physician"])
    assert exc.value.code == 2


def test_cli_inspect_rejects_unknown_release(tmp_path, capsys):
    assert main(["--knowledge-root", str(tmp_path), "inspect", "RXK-20261113T010101Z-ABCDEF12"]) == 2
    assert "release does not exist" in capsys.readouterr().out


def test_cli_exposes_task07_candidate_creation_and_decision(tmp_path, capsys):
    from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
    from services.evidence_review import record_review_decision

    staging = tmp_path / "staging"
    source = tmp_path / "evidence.json"
    source.write_text('{"evidence":"synthetic"}', encoding="utf-8")
    evidence = ingest_json_document(source, EvidenceMetadata(
        publisher="Synthetic", source_type="other", document_title="Synthetic fixture",
        canonical_url="https://api.fda.gov/cli/task07-fixture",
    ), staging)
    record_review_decision(evidence.record_id, "accepted_for_curation", "evidence-reviewer", "clinical_reviewer", "Synthetic accepted", staging)
    rule_file = tmp_path / "rule.json"
    rule_file.write_text(json.dumps({
        "medication":"metformin", "condition_or_population":"synthetic condition",
        "clinical_action":"synthetic action", "evidence_strength":"unknown", "source":"Synthetic",
        "conflict_status":"no_known_conflict",
    }), encoding="utf-8")
    curation = tmp_path / "curation"
    assert main(["--staging-root", str(staging), "--curation-root", str(curation), "candidate-create",
                 "--type", "contraindication", "--rule-file", str(rule_file), "--evidence-id", evidence.record_id,
                 "--author-id", "author", "--rationale", "Synthetic rationale"]) == 0
    candidate = json.loads(capsys.readouterr().out)
    assert candidate["candidate_type"] == "contraindication"
    assert main(["--staging-root", str(staging), "--curation-root", str(curation), "candidate-decide",
                 candidate["candidate_id"], "--decision", "approved", "--reviewer-id", "doctor",
                 "--reviewer-role", "physician", "--rationale", "Synthetic independent review"]) == 0
    decision = json.loads(capsys.readouterr().out)
    assert decision["decision"] == "approved"


def test_cli_requires_rollback_rationale():
    with pytest.raises(SystemExit) as exc:
        main(["rollback", "RXK-20261113T010101Z-ABCDEF12", "--actor-id", "steward",
              "--actor-role", "knowledge_steward"])
    assert exc.value.code == 2


def test_cli_exposes_release_review_commands(tmp_path, capsys):
    from scripts.manage_knowledge import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "--knowledge-root", str(tmp_path), "release-review", "RXK-20261113T010101Z-ABCDEF12",
        "--reviewer-id", "pharmacist-01", "--reviewer-role", "clinical_pharmacist",
        "--review-type", "clinical_release", "--decision", "approved", "--rationale", "test only",
    ])
    assert args.command == "release-review"
    assert args.review_type == "clinical_release"
