from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from services.evidence_ingestion import (
    MAX_DOCUMENT_BYTES,
    EvidenceMetadata,
    ingest_json_document,
)


@pytest.fixture()
def metadata() -> EvidenceMetadata:
    return EvidenceMetadata(
        publisher="U.S. Food and Drug Administration",
        source_type="fda_label",
        document_title="Synthetic label fixture",
        canonical_url="https://api.fda.gov/drug/label.json?search=synthetic",
        publication_date="2026-01-15",
        jurisdiction="US",
    )


@pytest.fixture()
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "source.json"
    path.write_text(json.dumps({"results": [{"id": "synthetic-1"}]}), encoding="utf-8")
    return path


def test_ingests_valid_json_to_review_only_staging(source_file, metadata, tmp_path):
    staging = tmp_path / "staging"
    result = ingest_json_document(source_file, metadata, staging)

    assert result.record_id.startswith("EVD-")
    assert result.source_id.startswith("SRC-INGEST-")
    assert result.duplicate is False
    assert result.review_status == "pending_clinical_review"
    assert result.promotion_status == "staged_only"

    artifact = json.loads(Path(result.artifact_path).read_text(encoding="utf-8"))
    assert artifact["payload"] == {"results": [{"id": "synthetic-1"}]}
    assert artifact["content_sha256"] == hashlib.sha256(source_file.read_bytes()).hexdigest()
    assert artifact["metadata"]["canonical_url"] == metadata.canonical_url
    assert artifact["review_status"] == "pending_clinical_review"
    assert artifact["promotion_status"] == "staged_only"

    index = json.loads((staging / "index.json").read_text(encoding="utf-8"))
    assert len(index["records"]) == 1
    assert index["records"][0]["record_id"] == result.record_id


def test_same_source_and_content_is_idempotent(source_file, metadata, tmp_path):
    first = ingest_json_document(source_file, metadata, tmp_path / "staging")
    second = ingest_json_document(source_file, metadata, tmp_path / "staging")

    assert first.record_id == second.record_id
    assert first.content_sha256 == second.content_sha256
    assert second.duplicate is True
    index = json.loads((tmp_path / "staging" / "index.json").read_text(encoding="utf-8"))
    assert len(index["records"]) == 1


def test_changed_content_creates_a_new_immutable_evidence_record(source_file, metadata, tmp_path):
    first = ingest_json_document(source_file, metadata, tmp_path / "staging")
    source_file.write_text('{"results":[{"id":"synthetic-2"}]}', encoding="utf-8")
    second = ingest_json_document(source_file, metadata, tmp_path / "staging")

    assert first.record_id != second.record_id
    assert first.content_sha256 != second.content_sha256
    assert first.source_id == second.source_id
    assert len(list((tmp_path / "staging" / first.source_id).glob("*.json"))) == 2


@pytest.mark.parametrize("url", [
    "http://api.fda.gov/drug/label.json",
    "https://api.fda.gov.attacker.example/drug/label.json",
    "https://user:password@api.fda.gov/drug/label.json",
    "https://api.fda.gov:8443/drug/label.json",
    "https://api.fda.gov/drug/label.json#fragment",
])
def test_rejects_untrusted_or_malformed_source_urls(source_file, metadata, tmp_path, url):
    invalid = EvidenceMetadata(**{**metadata.__dict__, "canonical_url": url})
    with pytest.raises(ValueError):
        ingest_json_document(source_file, invalid, tmp_path / "staging")
    assert not (tmp_path / "staging" / "index.json").exists()


def test_rejects_non_json_document(source_file, metadata, tmp_path):
    source_file.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="valid UTF-8 JSON"):
        ingest_json_document(source_file, metadata, tmp_path / "staging")


def test_rejects_non_finite_json_constants(source_file, metadata, tmp_path):
    source_file.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="valid JSON"):
        ingest_json_document(source_file, metadata, tmp_path / "staging")


def test_rejects_empty_and_oversized_documents(source_file, metadata, tmp_path):
    source_file.write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        ingest_json_document(source_file, metadata, tmp_path / "staging")

    source_file.write_bytes(b" " * (MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(ValueError, match="exceeds"):
        ingest_json_document(source_file, metadata, tmp_path / "staging")


def test_rejects_invalid_publication_date(source_file, metadata, tmp_path):
    invalid = EvidenceMetadata(**{**metadata.__dict__, "publication_date": "15-01-2026"})
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        ingest_json_document(source_file, invalid, tmp_path / "staging")


def test_staging_does_not_modify_runtime_knowledge_datasets(source_file, metadata, tmp_path):
    project_root = Path(__file__).resolve().parent.parent
    before = {
        name: (project_root / "knowledge" / name).read_bytes()
        for name in ("interaction_rules.json", "food_rules.json", "evidence_sources.json")
    }
    ingest_json_document(source_file, metadata, tmp_path / "staging")
    after = {
        name: (project_root / "knowledge" / name).read_bytes()
        for name in before
    }
    assert after == before


def test_recovers_index_when_artifact_exists_but_index_was_not_written(source_file, metadata, tmp_path):
    staging = tmp_path / "staging"
    first = ingest_json_document(source_file, metadata, staging)
    (staging / "index.json").unlink()

    second = ingest_json_document(source_file, metadata, staging)
    assert second.duplicate is True
    index = json.loads((staging / "index.json").read_text(encoding="utf-8"))
    assert len(index["records"]) == 1
    assert index["records"][0]["record_id"] == first.record_id


def test_rejects_unknown_source_type(source_file, metadata, tmp_path):
    invalid = EvidenceMetadata(**{**metadata.__dict__, "source_type": "untrusted_blog"})
    with pytest.raises(ValueError, match="source_type must be one of"):
        ingest_json_document(source_file, invalid, tmp_path / "staging")


def test_same_content_cannot_silently_replace_source_metadata(source_file, metadata, tmp_path):
    staging = tmp_path / "staging"
    ingest_json_document(source_file, metadata, staging)
    conflicting = EvidenceMetadata(**{**metadata.__dict__, "publisher": "Different publisher"})
    with pytest.raises(ValueError, match="conflicting source metadata"):
        ingest_json_document(source_file, conflicting, staging)
