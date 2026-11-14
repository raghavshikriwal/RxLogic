# Task 16 — External Medication Knowledge Integration

## Initial implementation increment

### Added
- Modular connector adapters for RxNorm/RxNav, DailyMed and openFDA, reusing
  the existing bounded `MedicalSourceClient` and evidence ingestion workflow.
- Source capability registry with source jurisdiction and implementation
  status.
- MedlinePlus Connect RxCUI reference URL helper; article content is not copied.
- India regulatory connector scaffold that explicitly reports not configured
  until an approved official machine-readable source is identified.
- External lookup orchestration with source allowlisting, query validation,
  refresh support and a 15-minute per-process TTL cache.
- Rate-limited endpoints:
  - `GET /api/external-knowledge/sources`
  - `POST /api/external-knowledge/search`
- User-triggered external lookup UI within the Task 15 medication profile card.
- Unit tests for staging-only behavior, source failures, cache behavior, input
  validation, India source status and MedlinePlus reference URL validation.
- Task 16 architecture documentation.

### Governance guarantees
- Retrieved snapshots remain `pending_clinical_review` and `staged_only`.
- No automatic evidence acceptance, clinical approval, candidate creation,
  knowledge release, or promotion is performed.
- Existing Task 15 approved-profile behavior remains the only path for approved
  findings.

### Not yet implemented
- Full SPL document retrieval and product-level label extraction.
- Normalized section candidate previews for all 13 Task 15 profile sections.
- Automated formulation applicability matching beyond the existing RxNorm
  concept lookup.
- A configured Indian regulatory API/source connector.
- Shared cross-worker persistent caching.
- Authenticated web-based clinical reviewer/approver identity.

This changelog records implementation scope, not clinical validation. No
clinical assertion has been added or approved by this increment.

## DailyMed full-label extraction increment

### Added
- DailyMed v2 SPL search followed by bounded retrieval of up to five individual
  SPL XML documents per lookup.
- XML parsing of SPL section identifiers, display names, section titles and
  verbatim section text, including namespaced documents.
- Separate immutable evidence staging for each retrieved label, preserving the
  original XML text, SET ID, label title, SPL version, publication date when
  parseable, product-label identity, section locators and retrieval metadata.
- Explicit product-applicability review marker; extraction does not infer that
  a label applies to every strength or formulation of an ingredient.
- A review-only no-match artifact when DailyMed returns no usable label rows.
- Parser tests for verbatim section text, code/title locators, nested XML and
  malformed XML rejection.

### Verification in this implementation environment
- Python compilation: passed.
- Focused external knowledge, evidence ingestion and evidence review tests:
  **35 passed**.
- Full backend suite could not be collected because Flask is not installed in
  this implementation environment. No full-suite result is claimed.
- No live DailyMed request was made; API retrieval behavior still requires
  mocked HTTP integration tests and a controlled live smoke test.

### Remaining work
- Add automated end-to-end tests for the multi-label HTTP retrieval and staging
  path, including HTTP failures, size limits, duplicate labels and malformed XML.
- Map SPL section codes/titles into the existing Task 15 canonical domain IDs
  as *candidate previews* without creating approved assertions.
- Complete formulation/strength matching and explicit ambiguity handling.
- Run full backend and frontend regression suites in the user's Windows venv.

## DailyMed extraction and section-preview increment

- DailyMed search results now lead to bounded retrieval of individual SPL XML documents using validated SPL SET IDs.
- Verbatim section text, SPL section codes/titles, label title, SET ID, version and available publication date are preserved in review-only evidence payloads.
- Added deterministic section mapping previews for supported Task 15 domains: indications, dosage/administration, contraindications, warnings/precautions and adverse reactions.
- Added integrity-verified preview loading for staged DailyMed evidence. Previews preserve source locators and excerpts but do not create curation records, clinical assertions, reviewer decisions or releases.
- Unknown or ambiguous sections remain explicitly unmapped for human classification.
- All extracted records remain `pending_clinical_review` and `staged_only`.
