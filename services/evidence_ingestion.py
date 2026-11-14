"""
Controlled ingestion of externally sourced JSON evidence into a review-only staging area.

This module deliberately does not create or modify interaction/food rules. An
ingested document is an evidence artifact, not a clinically approved assertion.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_STAGING_ROOT = Path(__file__).resolve().parent.parent / "knowledge" / "ingestion" / "staging"
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_URL_LENGTH = 2048
SCHEMA_VERSION = "1.0.0"
ALLOWED_SOURCE_TYPES = frozenset({
    "fda_label", "rxnorm_concept", "dailymed_spl", "clinical_guideline", "systematic_review", "regulatory_notice", "other"
})

# Restrict provenance URLs to official/primary-source domains. Subdomains are
# accepted, but lookalike suffixes (e.g. fda.gov.attacker.example) are not.
ALLOWED_SOURCE_DOMAINS = frozenset({
    "fda.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "dailymed.nlm.nih.gov",
    "rxnav.nlm.nih.gov",
    "open.fda.gov",
    "api.fda.gov",
    "doi.org",
    "cdsco.gov.in",
    "cdscoonline.gov.in",
})


@dataclass(frozen=True)
class EvidenceMetadata:
    publisher: str
    source_type: str
    document_title: str
    canonical_url: str
    publication_date: str | None = None
    jurisdiction: str | None = None


@dataclass(frozen=True)
class IngestionResult:
    record_id: str
    source_id: str
    content_sha256: str
    artifact_path: str
    duplicate: bool
    source_response_sha256: str = ""
    normalized_payload_sha256: str = ""
    source_bytes_path: str = ""
    review_status: str = "pending_clinical_review"
    promotion_status: str = "staged_only"


def _clean_required(value: str, field: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} is required")
    if len(cleaned) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    return cleaned


def _validate_metadata(metadata: EvidenceMetadata) -> EvidenceMetadata:
    publisher = _clean_required(metadata.publisher, "publisher", 200)
    source_type = _clean_required(metadata.source_type, "source_type", 64).lower()
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError(f"source_type must be one of: {', '.join(sorted(ALLOWED_SOURCE_TYPES))}")
    title = _clean_required(metadata.document_title, "document_title", 500)
    url = _clean_required(metadata.canonical_url, "canonical_url", MAX_URL_LENGTH)
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() != "https" or not host:
        raise ValueError("canonical_url must be an absolute HTTPS URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("canonical_url must not contain credentials or a fragment")
    if parsed.port not in (None, 443):
        raise ValueError("canonical_url must use the standard HTTPS port")
    if not any(host == domain or host.endswith("." + domain) for domain in ALLOWED_SOURCE_DOMAINS):
        raise ValueError(f"canonical_url host {host!r} is not an approved source domain")
    publication_date = metadata.publication_date
    if publication_date is not None:
        publication_date = _clean_required(publication_date, "publication_date", 10)
        try:
            date.fromisoformat(publication_date)
        except ValueError as exc:
            raise ValueError("publication_date must use YYYY-MM-DD") from exc
    jurisdiction = metadata.jurisdiction
    if jurisdiction is not None:
        jurisdiction = _clean_required(jurisdiction, "jurisdiction", 100)
    return EvidenceMetadata(
        publisher=publisher,
        source_type=source_type,
        document_title=title,
        canonical_url=url,
        publication_date=publication_date,
        jurisdiction=jurisdiction,
    )


def _reject_non_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON numeric constant: {value}")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def ingest_json_document(
    document_path: Path,
    metadata: EvidenceMetadata,
    staging_root: Path = DEFAULT_STAGING_ROOT,
) -> IngestionResult:
    """
    Validate and stage one JSON source snapshot.

    The resulting artifact is immutable-by-content-address and remains outside
    the runtime knowledge datasets. This function never promotes evidence or
    changes medication rules.
    """
    source_path = Path(document_path)
    try:
        size = source_path.stat().st_size
    except OSError as exc:
        raise ValueError(f"Cannot access evidence document: {exc}") from exc
    if not source_path.is_file():
        raise ValueError("Evidence document must be a regular file")
    if size <= 0:
        raise ValueError("Evidence document is empty")
    if size > MAX_DOCUMENT_BYTES:
        raise ValueError(f"Evidence document exceeds {MAX_DOCUMENT_BYTES} bytes")

    validated = _validate_metadata(metadata)
    try:
        raw = source_path.read_bytes()
        if len(raw) > MAX_DOCUMENT_BYTES:
            raise ValueError(f"Evidence document exceeds {MAX_DOCUMENT_BYTES} bytes")
        payload: Any = json.loads(raw.decode("utf-8"), parse_constant=_reject_non_json_constant)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Evidence document must be valid UTF-8 JSON: {exc}") from exc
    except ValueError as exc:
        if str(exc).startswith("Invalid JSON numeric constant"):
            raise ValueError(f"Evidence document must be valid JSON: {exc}") from exc
        raise

    digest = hashlib.sha256(raw).hexdigest()
    normalized_bytes = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)).encode("utf-8")
    normalized_digest = hashlib.sha256(normalized_bytes).hexdigest()
    metadata_bytes = json.dumps(asdict(validated), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    metadata_digest = hashlib.sha256(metadata_bytes).hexdigest()
    source_digest = hashlib.sha256(validated.canonical_url.encode("utf-8")).hexdigest()[:12].upper()
    source_id = f"SRC-INGEST-{source_digest}"
    record_digest = hashlib.sha256(
        f"{validated.canonical_url}\n{digest}".encode("utf-8")
    ).hexdigest()[:16].upper()
    record_id = f"EVD-{record_digest}"

    root = Path(staging_root).resolve()
    source_directory = root / source_id
    if source_directory.is_symlink():
        raise ValueError("Staging source directory must not be a symbolic link")
    source_directory.mkdir(parents=True, exist_ok=True)
    artifact = source_directory / f"{digest}.json"
    source_bytes_artifact = source_directory / f"{digest}.source.bin"
    if artifact.is_symlink():
        raise ValueError("Evidence artifact must not be a symbolic link")
    index_path = root / "index.json"
    duplicate = artifact.exists()
    existing_envelope: dict[str, Any] | None = None
    if duplicate:
        try:
            existing_envelope = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot verify existing evidence envelope: {exc}") from exc
        if existing_envelope.get("metadata", {}) != asdict(validated):
            raise ValueError("Duplicate evidence content has conflicting source metadata; use a distinct source record and review it separately")
        existing_metadata_bytes = json.dumps(existing_envelope.get("metadata", {}), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        existing_metadata_digest = hashlib.sha256(existing_metadata_bytes).hexdigest()
        if existing_envelope.get("metadata_sha256") and existing_envelope["metadata_sha256"] != existing_metadata_digest:
            raise ValueError("Existing evidence metadata hash verification failed")
        if existing_envelope.get("source_response_sha256", existing_envelope.get("content_sha256")) != digest:
            raise ValueError("Existing evidence source-response hash verification failed")
        existing_payload_bytes = json.dumps(existing_envelope.get("payload"), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if hashlib.sha256(existing_payload_bytes).hexdigest() != normalized_digest:
            raise ValueError("Existing evidence normalized-payload hash verification failed")
    captured_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "source_id": source_id,
        "metadata": asdict(validated),
        "retrieved_at": captured_at,
        "content_sha256": digest,
        "source_response_sha256": digest,
        "normalized_payload_sha256": normalized_digest,
        "metadata_sha256": metadata_digest,
        "source_bytes_artifact": f"{source_id}/{digest}.source.bin",
        "content_bytes": len(raw),
        "review_status": "pending_clinical_review",
        "promotion_status": "staged_only",
        "payload": payload,
    }
    encoded = (json.dumps(envelope, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")

    # The source artifact is written before the index. A crash between writes
    # leaves a recoverable artifact rather than an index pointing to no file.
    if not duplicate:
        _atomic_write(artifact, encoded)
    if not source_bytes_artifact.exists():
        _atomic_write(source_bytes_artifact, raw)
    index: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "records": []}
    if index_path.exists():
        try:
            loaded = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read ingestion index: {exc}") from exc
        if (
            not isinstance(loaded, dict)
            or loaded.get("schema_version") != SCHEMA_VERSION
            or not isinstance(loaded.get("records"), list)
            or any(not isinstance(item, dict) for item in loaded["records"])
        ):
            raise ValueError("Ingestion index has an invalid structure or schema version")
        index = loaded
    existing_record = next(
        (item for item in index["records"] if item.get("record_id") == record_id),
        None,
    )
    index_changed = False
    if existing_record is not None and existing_record.get("metadata_sha256") not in (None, metadata_digest):
        raise ValueError("Existing evidence index binds different source metadata; refusing to replace provenance")
    if existing_record is None:
        new_record = {
            "record_id": record_id,
            "source_id": source_id,
            "content_sha256": digest,
            "source_response_sha256": digest,
            "normalized_payload_sha256": normalized_digest,
            "source_bytes_artifact": f"{source_id}/{digest}.source.bin",
            "artifact": f"{source_id}/{digest}.json",
            "retrieved_at": captured_at,
            "review_status": "pending_clinical_review",
            "promotion_status": "staged_only",
        }
        bound_metadata_digest = (
            ((existing_envelope or {}).get("metadata_sha256") or existing_metadata_digest)
            if duplicate else metadata_digest
        )
        if bound_metadata_digest:
            new_record["metadata_sha256"] = bound_metadata_digest
        index["records"].append(new_record)
        index_changed = True
    else:
        # Content-identical bytes must not allow source provenance to be silently
        # replaced. The immutable envelope was verified above.
        envelope_metadata_digest = (
            ((existing_envelope or {}).get("metadata_sha256") or existing_metadata_digest)
            if duplicate else metadata_digest
        )
        for key, value in {
            "source_response_sha256": digest,
            "normalized_payload_sha256": normalized_digest,
            "source_bytes_artifact": f"{source_id}/{digest}.source.bin",
        }.items():
            if existing_record.get(key) != value:
                existing_record[key] = value
                index_changed = True
        if envelope_metadata_digest and existing_record.get("metadata_sha256") != envelope_metadata_digest:
            existing_record["metadata_sha256"] = envelope_metadata_digest
            index_changed = True
    if index_changed:
        index["records"].sort(key=lambda item: (item.get("source_id", ""), item.get("record_id", "")))
        _atomic_write(
            index_path,
            (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )

    return IngestionResult(
        record_id=record_id,
        source_id=source_id,
        content_sha256=digest,
        artifact_path=str(artifact),
        source_response_sha256=digest,
        normalized_payload_sha256=normalized_digest,
        source_bytes_path=str(source_bytes_artifact),
        duplicate=duplicate,
    )
