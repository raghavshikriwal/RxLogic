from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
from services.evidence_review import (
    EvidenceReviewError,
    inspect_evidence,
    list_review_queue,
    record_review_decision,
)


@pytest.fixture()
def staged(tmp_path):
    source = tmp_path / "source.json"
    raw = b'{ "results" : [{"id":"synthetic","value":1}] }\n'
    source.write_bytes(raw)
    metadata = EvidenceMetadata(
        publisher="U.S. Food and Drug Administration",
        source_type="fda_label",
        document_title="Synthetic review fixture",
        canonical_url="https://api.fda.gov/drug/label.json?review-fixture=1",
    )
    root = tmp_path / "staging"
    result = ingest_json_document(source, metadata, root)
    return root, result, raw


def test_ingestion_preserves_original_bytes_and_separate_hashes(staged):
    root, result, raw = staged
    assert Path(result.source_bytes_path).read_bytes() == raw
    assert result.source_response_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.normalized_payload_sha256 != result.source_response_sha256
    artifact = json.loads(Path(result.artifact_path).read_text())
    assert artifact["source_response_sha256"] == result.source_response_sha256
    assert artifact["normalized_payload_sha256"] == result.normalized_payload_sha256
    assert artifact["source_bytes_artifact"].endswith(".source.bin")


def test_review_queue_and_inspection_verify_evidence(staged):
    root, result, raw = staged
    queue = list_review_queue(root)
    assert [item["record_id"] for item in queue] == [result.record_id]
    inspected = inspect_evidence(result.record_id, root)
    assert inspected["source_bytes"] == len(raw)
    assert inspected["source_response_sha256"] == result.source_response_sha256
    assert inspected["normalized_payload_sha256"] == result.normalized_payload_sha256
    assert inspected["promotion_status"] == "staged_only"


def test_decisions_are_append_only_and_latest_decision_drives_queue(staged):
    root, result, _ = staged
    artifact_before = Path(result.artifact_path).read_bytes()
    first = record_review_decision(
        result.record_id, "request_more_evidence", "reviewer-01",
        "clinical_reviewer", "Need a current primary source.", root,
    )
    second = record_review_decision(
        result.record_id, "accepted_for_curation", "reviewer-02",
        "clinical_pharmacist", "Source and payload hashes verified; suitable for curation review.", root,
    )
    ledger = (root / "review_decisions.jsonl").read_text().splitlines()
    assert len(ledger) == 2
    assert json.loads(ledger[0])["decision_id"] == first["decision_id"]
    assert json.loads(ledger[1])["decision_id"] == second["decision_id"]
    assert list_review_queue(root) == []
    assert list_review_queue(root, "accepted_for_curation")[0]["record_id"] == result.record_id
    assert list_review_queue(root, "all")[0]["promotion_status"] == "staged_only"
    assert Path(result.artifact_path).read_bytes() == artifact_before
    assert not (root.parent / "interaction_rules.json").exists()


def test_rejects_invalid_reviewer_or_decision(staged):
    root, result, _ = staged
    with pytest.raises(EvidenceReviewError, match="reviewer_id"):
        record_review_decision(result.record_id, "rejected", "", "physician", "Reason", root)
    with pytest.raises(EvidenceReviewError, match="reviewer_role"):
        record_review_decision(result.record_id, "rejected", "r1", "visitor", "Reason", root)
    with pytest.raises(EvidenceReviewError, match="decision must"):
        record_review_decision(result.record_id, "approved", "r1", "physician", "Reason", root)


def test_requires_rationale_and_existing_record(staged):
    root, result, _ = staged
    with pytest.raises(EvidenceReviewError, match="rationale"):
        record_review_decision(result.record_id, "rejected", "r1", "physician", " ", root)
    with pytest.raises(EvidenceReviewError, match="not found"):
        inspect_evidence("EVD-NOT-REAL", root)


def test_detects_tampered_original_source_bytes(staged):
    root, result, _ = staged
    Path(result.source_bytes_path).write_bytes(b'{"tampered":true}')
    with pytest.raises(EvidenceReviewError, match="source-response hash"):
        inspect_evidence(result.record_id, root)


def test_detects_tampered_normalized_payload(staged):
    root, result, _ = staged
    artifact_path = Path(result.artifact_path)
    artifact = json.loads(artifact_path.read_text())
    artifact["payload"]["tampered"] = True
    artifact_path.write_text(json.dumps(artifact))
    with pytest.raises(EvidenceReviewError, match="Normalized payload hash"):
        inspect_evidence(result.record_id, root)


def test_legacy_record_can_be_repaired_by_exact_reingestion(staged, tmp_path):
    root, result, raw = staged
    artifact_path = Path(result.artifact_path)
    artifact = json.loads(artifact_path.read_text())
    artifact.pop("source_response_sha256", None)
    artifact.pop("normalized_payload_sha256", None)
    artifact.pop("source_bytes_artifact", None)
    artifact.pop("metadata_sha256", None)
    artifact_path.write_text(json.dumps(artifact))
    index_path = root / "index.json"
    index = json.loads(index_path.read_text())
    for key in ("source_response_sha256", "normalized_payload_sha256", "source_bytes_artifact", "metadata_sha256"):
        index["records"][0].pop(key, None)
    index_path.write_text(json.dumps(index))
    # Re-ingest the exact original response; this restores the source sidecar
    # and adds verifiable hash metadata to the index without rewriting the artifact.
    source = tmp_path / "source.json"
    source.write_bytes(raw)
    metadata = EvidenceMetadata(
        publisher="U.S. Food and Drug Administration",
        source_type="fda_label",
        document_title="Synthetic review fixture",
        canonical_url="https://api.fda.gov/drug/label.json?review-fixture=1",
    )
    repaired = ingest_json_document(source, metadata, root)
    assert repaired.duplicate is True
    inspected = inspect_evidence(result.record_id, root)
    assert inspected["source_response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert inspected["metadata_integrity"] == "verified"


def test_review_binds_source_metadata_to_integrity_digest(staged):
    root, result, _ = staged
    inspected = inspect_evidence(result.record_id, root)
    assert inspected["metadata_integrity"] == "verified"
    decision = record_review_decision(result.record_id, "accepted_for_curation", "reviewer", "clinical_reviewer", "Synthetic review", root)
    assert decision["metadata_sha256"] == inspected["metadata_sha256"]
    artifact_path = Path(result.artifact_path)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["metadata"]["publisher"] = "Tampered publisher"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    with pytest.raises(EvidenceReviewError, match="metadata hash"):
        inspect_evidence(result.record_id, root)
