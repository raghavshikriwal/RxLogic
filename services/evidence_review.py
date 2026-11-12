"""Auditable, review-only workflow for staged medical evidence.

This module records decisions separately from immutable evidence artifacts. It
never creates, edits, or promotes runtime medication/food knowledge rules.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from services.evidence_ingestion import DEFAULT_STAGING_ROOT, SCHEMA_VERSION, EvidenceMetadata, _validate_metadata

DECISION_FILE = "review_decisions.jsonl"
VALID_DECISIONS = frozenset({"accepted_for_curation", "rejected", "request_more_evidence"})
VALID_ROLES = frozenset({"clinical_reviewer", "clinical_pharmacist", "physician", "knowledge_steward", "administrator"})


class EvidenceReviewError(ValueError):
    """Raised when an evidence review operation is invalid or unsafe."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceReviewError(f"Cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceReviewError(f"{path.name} must contain a JSON object")
    return value


def _load_index(root: Path) -> dict[str, Any]:
    index = _read_json(root / "index.json")
    if index.get("schema_version") != SCHEMA_VERSION or not isinstance(index.get("records"), list):
        raise EvidenceReviewError("Evidence index has an unsupported or invalid schema")
    return index


def _safe_artifact_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise EvidenceReviewError("Evidence artifact path is missing")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise EvidenceReviewError("Evidence artifact path is invalid")
    path = root.joinpath(*rel.parts)
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise EvidenceReviewError("Evidence artifact path escapes the staging directory")
    return path


def _records(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    index = _load_index(root)
    decisions = _load_decisions(root)
    latest: dict[str, dict[str, Any]] = {}
    for item in decisions:
        latest[item["record_id"]] = item
    result = []
    for record in index["records"]:
        if not isinstance(record, dict) or not isinstance(record.get("record_id"), str):
            raise EvidenceReviewError("Evidence index contains an invalid record")
        item = dict(record)
        decision = latest.get(item["record_id"])
        item["review_status"] = decision["decision"] if decision else "pending_clinical_review"
        item["latest_decision"] = decision
        item["promotion_status"] = "staged_only"
        result.append(item)
    return index, result


def _load_decisions(root: Path) -> list[dict[str, Any]]:
    path = root / DECISION_FILE
    if not path.exists():
        return []
    if path.is_symlink():
        raise EvidenceReviewError("Review decision ledger must not be a symbolic link")
    entries: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict) or not isinstance(item.get("record_id"), str):
                    raise ValueError("invalid decision entry")
                entries.append(item)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise EvidenceReviewError(f"Review decision ledger is invalid: {exc}") from exc
    return entries


def list_review_queue(staging_root: Path = DEFAULT_STAGING_ROOT, status: str = "pending_clinical_review") -> list[dict[str, Any]]:
    """Return evidence records filtered by their latest review decision."""
    root = Path(staging_root).resolve()
    _, records = _records(root)
    if status == "all":
        return records
    if status not in {"pending_clinical_review", *VALID_DECISIONS}:
        raise EvidenceReviewError("Unknown review status")
    return [record for record in records if record["review_status"] == status]


def inspect_evidence(record_id: str, staging_root: Path = DEFAULT_STAGING_ROOT) -> dict[str, Any]:
    """Load evidence and verify both original and normalized content hashes."""
    root = Path(staging_root).resolve()
    matches = [r for r in list_review_queue(root, "all") if r["record_id"] == record_id]
    if not matches:
        raise EvidenceReviewError(f"Evidence record not found: {record_id}")
    record = matches[0]
    artifact_path = _safe_artifact_path(root, record["artifact"])
    artifact = _read_json(artifact_path)
    source_rel = artifact.get("source_bytes_artifact") or record.get("source_bytes_artifact")
    if not source_rel:
        raise EvidenceReviewError("Original source bytes are unavailable for this legacy evidence record")
    source_path = _safe_artifact_path(root, source_rel)
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise EvidenceReviewError(f"Cannot read original source bytes: {exc}") from exc
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    expected_source_hash = artifact.get("source_response_sha256", artifact.get("content_sha256")) or record.get("source_response_sha256", record.get("content_sha256"))
    if source_hash != expected_source_hash:
        raise EvidenceReviewError("Original source-response hash verification failed")
    normalized = json.dumps(artifact.get("payload"), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    normalized_hash = hashlib.sha256(normalized).hexdigest()
    expected_normalized = artifact.get("normalized_payload_sha256") or record.get("normalized_payload_sha256")
    if expected_normalized and normalized_hash != expected_normalized:
        raise EvidenceReviewError("Normalized payload hash verification failed")
    metadata = artifact.get("metadata", {})
    if not isinstance(metadata, dict):
        raise EvidenceReviewError("Evidence metadata must be an object")
    try:
        validated_metadata = _validate_metadata(EvidenceMetadata(**metadata))
    except (TypeError, ValueError) as exc:
        raise EvidenceReviewError(f"Evidence metadata is invalid: {exc}") from exc
    if asdict(validated_metadata) != metadata:
        raise EvidenceReviewError("Evidence metadata is not in canonical validated form")
    metadata_bytes = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    metadata_hash = hashlib.sha256(metadata_bytes).hexdigest()
    expected_metadata_hash = artifact.get("metadata_sha256") or record.get("metadata_sha256")
    if expected_metadata_hash and metadata_hash != expected_metadata_hash:
        raise EvidenceReviewError("Evidence metadata hash verification failed")
    return {
        "record": record,
        "metadata": metadata,
        "metadata_sha256": metadata_hash,
        "metadata_integrity": "verified" if expected_metadata_hash else "legacy_unbound",
        "payload": artifact.get("payload"),
        "source_response_sha256": source_hash,
        "normalized_payload_sha256": normalized_hash,
        "source_bytes": len(source_bytes),
        "retrieved_at": artifact.get("retrieved_at"),
        "promotion_status": "staged_only",
    }


def record_review_decision(
    record_id: str,
    decision: str,
    reviewer_id: str,
    reviewer_role: str,
    rationale: str,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Append a review decision; never alter evidence or runtime knowledge."""
    if decision not in VALID_DECISIONS:
        raise EvidenceReviewError(f"decision must be one of: {', '.join(sorted(VALID_DECISIONS))}")
    if not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id.strip()) > 200:
        raise EvidenceReviewError("reviewer_id is required and must be at most 200 characters")
    if reviewer_role not in VALID_ROLES:
        raise EvidenceReviewError(f"reviewer_role must be one of: {', '.join(sorted(VALID_ROLES))}")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale.strip()) > 4000:
        raise EvidenceReviewError("rationale is required and must be at most 4000 characters")
    root = Path(staging_root).resolve()
    evidence = inspect_evidence(record_id, root)
    prior = evidence["record"].get("latest_decision")
    if prior and prior.get("decision") == decision and prior.get("reviewer_id") == reviewer_id.strip() and prior.get("rationale") == rationale.strip():
        return prior
    entry = {
        "schema_version": SCHEMA_VERSION,
        "decision_id": "REV-" + hashlib.sha256(f"{record_id}|{datetime.now(timezone.utc).isoformat()}|{reviewer_id}".encode()).hexdigest()[:16].upper(),
        "record_id": record_id,
        "decision": decision,
        "reviewer_id": reviewer_id.strip(),
        "reviewer_role": reviewer_role,
        "reviewed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "rationale": rationale.strip(),
        "request_id": request_id.strip() if isinstance(request_id, str) and request_id.strip() else None,
        "source_response_sha256": evidence["source_response_sha256"],
        "normalized_payload_sha256": evidence["normalized_payload_sha256"],
        "metadata_sha256": evidence["metadata_sha256"],
        "promotion_status": "staged_only",
    }
    path = root / DECISION_FILE
    if path.is_symlink():
        raise EvidenceReviewError("Review decision ledger must not be a symbolic link")
    root.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(entry, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    # O_APPEND ensures each decision is appended, never rewriting prior history.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "ab") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise
    return entry
