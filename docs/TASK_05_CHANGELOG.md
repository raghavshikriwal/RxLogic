# Task 05 — Evidence review and approval workflow

## Status

Implementation candidate. Awaiting full Windows verification before Task 05 is marked complete.

## Changes

- Preserves each newly ingested source response byte-for-byte in a sibling `.source.bin` file. The sidecar deliberately does not use a `.json` extension, so JSON-only artifact discovery remains unambiguous.
- Records separate SHA-256 fingerprints for the original source response and the canonical normalized JSON payload. `content_sha256` remains as a backwards-compatible alias for the source-response hash.
- Adds a review queue and evidence inspection service. Inspection verifies both hashes before exposing the normalized payload to a reviewer.
- Task 07 extends the evidence envelope and review decision with a separate canonical `metadata_sha256` fingerprint, preventing source publisher/title/jurisdiction/URL metadata from being silently altered after review. Legacy records without the fingerprint remain inspectable but must be re-ingested and re-reviewed before new curation.
- Adds explicit review decisions: `accepted_for_curation`, `rejected`, and `request_more_evidence`.
- Requires reviewer identity, an allowlisted reviewer role, and a non-empty rationale.
- Stores decisions in `review_decisions.jsonl` as append-only records. The latest decision determines the queue status; earlier decisions remain in history.
- Adds `scripts.review_evidence` CLI commands for queue, show, and decide.
- Review acceptance is only acceptance for a later curation step. It does not create a clinical rule, approve a treatment recommendation, or change active knowledge.

## Important compatibility note

Task 04 staging records predate source-byte sidecars. Their original response bytes cannot be reconstructed reliably from normalized payloads. They remain visible in the queue, but inspection/review refuses to proceed until those source records are re-fetched and ingested with Task 05. Existing snapshots are not rewritten.

## Commands

```powershell
python -m scripts.review_evidence queue
python -m scripts.review_evidence queue --status all
python -m scripts.review_evidence show EVD-<record-id>
python -m scripts.review_evidence decide EVD-<record-id> accepted_for_curation `
  --reviewer-id reviewer-001 `
  --reviewer-role clinical_pharmacist `
  --rationale "Verified source passage, population, formulation and date."
```

Supported roles: `clinical_reviewer`, `clinical_pharmacist`, `physician`, `knowledge_steward`, `administrator`.

## Validation performed in the build environment

- `tests/test_evidence_ingestion.py` and `tests/test_evidence_review.py`: 22 passed.
- Full suite collection is currently blocked in this environment because Flask and scikit-fuzzy are not installed. This is an environment dependency issue; it is not reported as a passing full-suite run.

## Clinical governance boundary

No automatic rule creation or promotion is implemented. `accepted_for_curation` means only that a reviewer has made the evidence eligible for a separate Task 06 curation workflow. It is not a clinical approval of a medication interaction assertion.
