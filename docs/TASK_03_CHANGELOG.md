# Task 03 — Evidence source ingestion

## Added

- `services/evidence_ingestion.py`: validates metadata and JSON snapshots,
  restricts canonical URLs to HTTPS primary-source domains, computes
  SHA-256 content hashes, and writes content-addressed evidence artifacts.
- `scripts/ingest_evidence.py`: command-line entry point for staging a locally
  downloaded source document with explicit provenance metadata.
- `knowledge/ingestion/README.md`: trust boundary, supported sources, and
  operator instructions.
- `tests/test_evidence_ingestion.py`: tests for valid ingestion, idempotency,
  changed-content versioning, URL validation, invalid/oversized inputs,
  non-finite JSON values, crash recovery, and runtime-data isolation.

## Safety and design decisions

- Ingestion is offline: it does not fetch user-supplied URLs and therefore
  introduces no SSRF-capable network path.
- Only HTTPS canonical URLs hosted by the configured primary-source domain
  allowlist are accepted.
- Each snapshot is stored by SHA-256 content digest. The index is an inventory,
  not the source of truth.
- Ingested evidence remains `pending_clinical_review` and `staged_only`.
- The ingestion path does not modify runtime rule datasets or infer clinical
  interactions from label text.
- No new clinical claims or medication rules were added.

## Validation boundary

Passing tests establishes software and data-integrity behavior only. It does
not verify that an imported source is authentic, current, complete, applicable,
or clinically correct. Manual clinical review remains mandatory before a
separate future curation workflow can update runtime knowledge.
