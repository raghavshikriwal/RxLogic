from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
from services.evidence_review import record_review_decision
from services.knowledge_curation import (
    CurationError,
    create_candidate,
    list_candidates,
    record_clinical_decision,
)


@pytest.fixture()
def accepted_evidence(tmp_path):
    source = tmp_path / "source.json"
    source.write_bytes(b'{ "evidence": "synthetic source text" }\n')
    metadata = EvidenceMetadata(
        publisher="U.S. Food and Drug Administration",
        source_type="fda_label",
        document_title="Synthetic candidate fixture",
        canonical_url="https://api.fda.gov/drug/label.json?curation-fixture=1",
    )
    staging = tmp_path / "staging"
    result = ingest_json_document(source, metadata, staging)
    record_review_decision(
        result.record_id, "accepted_for_curation", "evidence-reviewer",
        "clinical_reviewer", "Accepted for candidate curation only.", staging,
    )
    return staging, result


@pytest.fixture()
def interaction_rule():
    return {
        "medication_a": "warfarin",
        "medication_b": "aspirin",
        "severity": "severe",
        "evidence": "moderate",
        "description": "Synthetic test assertion; not clinical guidance.",
        "source": "Synthetic test source",
        "jurisdiction": "US",
    }


def test_candidate_requires_accepted_hash_verified_evidence(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    root = tmp_path / "curation"
    candidate = create_candidate(
        "interaction_rule", interaction_rule, [evidence.record_id], "author-1",
        "Human-authored test candidate.", staging, root,
    )
    assert candidate["candidate_status"] == "pending_clinical_approval"
    assert candidate["promotion_status"] == "not_promoted"
    assert candidate["evidence"][0]["record_id"] == evidence.record_id
    assert candidate["evidence"][0]["normalized_payload_sha256"]
    assert candidate["evidence"][0]["metadata_sha256"]
    assert (root / "candidates.jsonl").exists()


def test_pending_or_rejected_evidence_cannot_back_candidate(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    # A later decision supersedes acceptance; the latest state is authoritative.
    record_review_decision(
        evidence.record_id, "rejected", "reviewer-2", "clinical_reviewer",
        "Rejected in follow-up review.", staging,
    )
    with pytest.raises(CurationError, match="not currently accepted"):
        create_candidate("interaction_rule", interaction_rule, [evidence.record_id], "author", "Reason", staging, tmp_path / "curation")


def test_candidate_rejects_invalid_rule_and_duplicate_evidence(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    invalid = {**interaction_rule, "severity": "critical"}
    with pytest.raises(CurationError, match="severity"):
        create_candidate("interaction_rule", invalid, [evidence.record_id], "author", "Reason", staging, tmp_path / "curation")
    with pytest.raises(CurationError, match="duplicate"):
        create_candidate("interaction_rule", interaction_rule, [evidence.record_id, evidence.record_id], "author", "Reason", staging, tmp_path / "curation")


def test_independent_clinical_approval_required_and_does_not_promote(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    root = tmp_path / "curation"
    candidate = create_candidate("interaction_rule", interaction_rule, [evidence.record_id], "author-1", "Reason", staging, root)
    with pytest.raises(CurationError, match="cannot clinically approve"):
        record_clinical_decision(candidate["candidate_id"], "approved", "author-1", "physician", "Self approval", root, staging)
    with pytest.raises(CurationError, match="clinical_pharmacist or physician"):
        record_clinical_decision(candidate["candidate_id"], "approved", "reviewer", "knowledge_steward", "Not a clinical approver", root, staging)
    decision = record_clinical_decision(candidate["candidate_id"], "approved", "pharmacist-1", "clinical_pharmacist", "Independently reviewed for test only.", root, staging)
    assert decision["decision"] == "approved"
    current = list_candidates(root)[0]
    assert current["candidate_status"] == "approved"
    assert current["promotion_status"] == "not_promoted"


def test_approval_is_append_only_and_cannot_be_rewritten(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    root = tmp_path / "curation"
    candidate = create_candidate("interaction_rule", interaction_rule, [evidence.record_id], "author-1", "Reason", staging, root)
    record_clinical_decision(candidate["candidate_id"], "approved", "doctor-1", "physician", "Approved test fixture.", root, staging)
    with pytest.raises(CurationError, match="already clinically approved"):
        record_clinical_decision(candidate["candidate_id"], "rejected", "doctor-2", "physician", "Attempted rewrite", root, staging)
    assert len((root / "candidate_decisions.jsonl").read_text().splitlines()) == 1


def test_curation_never_modifies_runtime_knowledge_files(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    project = Path(__file__).resolve().parent.parent
    files = [project / "knowledge" / name for name in ("interaction_rules.json", "food_rules.json", "manifest.json")]
    before = [p.read_bytes() for p in files]
    root = tmp_path / "curation"
    candidate = create_candidate("interaction_rule", interaction_rule, [evidence.record_id], "author-1", "Reason", staging, root)
    record_clinical_decision(candidate["candidate_id"], "approved", "doctor-1", "physician", "Approved test fixture.", root, staging)
    assert [p.read_bytes() for p in files] == before


def test_clinical_approval_rechecks_latest_evidence_review_state(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    root = tmp_path / "curation"
    candidate = create_candidate("interaction_rule", interaction_rule, [evidence.record_id], "author-1", "Reason", staging, root)
    record_review_decision(
        evidence.record_id, "request_more_evidence", "reviewer-3", "clinical_reviewer",
        "New evidence requested after candidate drafting.", staging,
    )
    with pytest.raises(CurationError, match="not currently accepted"):
        record_clinical_decision(candidate["candidate_id"], "approved", "doctor-1", "physician", "Attempt approval", root, staging)


def test_metadata_tampering_after_evidence_acceptance_blocks_clinical_approval(accepted_evidence, interaction_rule, tmp_path):
    staging, evidence = accepted_evidence
    root = tmp_path / "curation"
    candidate = create_candidate("interaction_rule", interaction_rule, [evidence.record_id], "author-1", "Reason", staging, root)
    artifact_path = Path(evidence.artifact_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["metadata"]["publisher"] = "Tampered publisher"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(CurationError, match="metadata hash"):
        record_clinical_decision(candidate["candidate_id"], "approved", "doctor", "physician", "Review", root, staging)
