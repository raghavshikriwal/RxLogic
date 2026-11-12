# Evidence ingestion staging

This directory is reserved for evidence snapshots collected for human review.
The ingestion utility writes to `staging/` by default; generated snapshots are
ignored by Git and are not loaded by the runtime reasoning engine.

## Trust and safety boundary

- Only HTTPS URLs on the explicit primary-source allowlist are accepted.
- Input is limited to 10 MiB and must be valid UTF-8 JSON.
- Original response bytes, normalized JSON payload, and source metadata have
  separate SHA-256 fingerprints. Metadata integrity matters because publisher,
  title, jurisdiction, and canonical URL affect evidence provenance.
- A review decision binds all three fingerprints; changing source metadata after
  review invalidates the candidate path even if the response bytes are unchanged.
- Re-ingesting identical content from the same canonical URL is idempotent.
- A changed document creates a new immutable-by-content artifact.
- Every artifact is marked `pending_clinical_review` and `staged_only`.
- Ingestion never writes to `interaction_rules.json`, `food_rules.json`,
  `clinical_assertions.json`, or `evidence_sources.json`, and never promotes
  extracted statements into rules.
- Structural provenance is not evidence of clinical correctness. A qualified
  reviewer must verify the original source, relevant passage, population,
  formulation, jurisdiction, publication/update date, and applicability.

## CLI

Download a source document manually from an approved primary source, save the
JSON response locally, then run from the repository root:

```powershell
python -m scripts.ingest_evidence `
  --input .\downloads\example-label.json `
  --publisher "U.S. Food and Drug Administration" `
  --source-type fda_label `
  --title "Example label snapshot" `
  --url "https://api.fda.gov/drug/label.json?search=..." `
  --jurisdiction US
```

Optional metadata:

- `--publication-date YYYY-MM-DD`
- `--staging-dir PATH` (for isolated/test staging)

The command prints a record ID, source ID, digest, artifact path, and review
state. It does not fetch URLs or execute remote content. Review the source
document independently before any separate, controlled knowledge curation
process.

## Current approved URL hosts

`fda.gov`, `nih.gov`, `ncbi.nlm.nih.gov`, `pubmed.ncbi.nlm.nih.gov`,
`dailymed.nlm.nih.gov`, `rxnav.nlm.nih.gov`, `open.fda.gov`, `api.fda.gov`,
and `doi.org` (including their subdomains).

The allowlist is a provenance guardrail, not an endorsement of every page or
claim hosted by those organizations.


## Task 04: fetch from official APIs

See `docs/TASK_04_SOURCE_CONNECTORS.md` for the RxNav, openFDA, and DailyMed connector commands. Live responses are automatically passed into the same review-only staging process; they are never promoted into runtime rules.

## Task 05: evidence review

New ingestions preserve the exact original response bytes in a sibling
`.source.bin` sidecar. The evidence envelope and staging index carry two
separate fingerprints: `source_response_sha256` for the original bytes and
`normalized_payload_sha256` for the canonical normalized JSON payload.
`content_sha256` remains a compatibility alias for the source-response hash.

Review evidence from the repository root:

```powershell
python -m scripts.review_evidence queue
python -m scripts.review_evidence show EVD-<record-id>
python -m scripts.review_evidence decide EVD-<record-id> request_more_evidence `
  --reviewer-id reviewer-001 `
  --reviewer-role clinical_reviewer `
  --rationale "Need a current primary-source passage."
```

Decisions are appended to `staging/review_decisions.jsonl`; prior decisions
are retained. Available decisions are `accepted_for_curation`, `rejected`, and
`request_more_evidence`. Reviewer roles are `clinical_reviewer`,
`clinical_pharmacist`, `physician`, `knowledge_steward`, and `administrator`.

An accepted record remains `staged_only`. It is merely eligible for a later
controlled curation step; no interaction rule is created or activated. Task 04
records do not contain original response bytes. They must be re-fetched and
ingested before they can be reviewed, because normalized JSON cannot reliably
reconstruct the exact original response.

## Task 07 provenance binding

New evidence envelopes include `metadata_sha256` over canonical source metadata. The review ledger stores this fingerprint alongside the source-response and normalized-payload hashes. Candidate creation requires all three to match the latest accepted review. Legacy records without a metadata fingerprint remain inspectable but are not eligible for new candidates; re-ingest and re-review the original source to establish a current provenance binding. Re-ingestion of identical bytes with conflicting metadata is rejected rather than silently replacing the original source description.
