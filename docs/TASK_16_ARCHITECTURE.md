# Task 16 — External Medication Knowledge Integration

## Implementation status

This document describes the first implementation increment. It is not a claim
that all Task 16 acceptance criteria are complete. The current increment adds
modular orchestration around the existing Task 04 source client, an explicit
API trigger, source capability metadata, a review-only frontend control, and
unit tests. Product-level section extraction, jurisdiction-specific clinical
applicability, and a configured Indian regulatory data feed remain future work.

## Existing components reused

- `services/medical_source_client.py`: fixed-host, bounded HTTPS retrieval for
  RxNav, openFDA and DailyMed; source responses are staged using the existing
  immutable evidence-ingestion service.
- `services/evidence_ingestion.py`: original source bytes, normalized JSON,
  SHA-256 fingerprints, source metadata and `staged_only` state.
- `services/evidence_review.py`: append-only human review decisions.
- `services/knowledge_curation.py`: candidate creation after accepted evidence.
- `services/knowledge_release.py`: independent review, promotion and runtime
  integrity checks.
- `services/clinical_profile.py`: approved-only profile output.

No parallel evidence ledger or approval mechanism is introduced.

## New modules

- `services/external_sources/base.py`: connector result and capability contracts.
- `services/external_sources/rxnorm.py`: adapter for the existing RxNav fetcher.
- `services/external_sources/dailymed.py`: adapter for the existing DailyMed fetcher.
- `services/external_sources/openfda.py`: adapter for the existing openFDA fetcher.
- `services/external_sources/india_sources.py`: explicit not-configured capability;
  it does not invent an API or scrape CDSCO pages.
- `services/external_sources/medlineplus.py`: validated RxCUI-based Connect URL
  helper only. It does not download or redistribute MedlinePlus article content.
- `services/external_sources/registry.py`: source capability and jurisdiction list.
- `services/external_knowledge.py`: explicit lookup orchestration and a bounded
  15-minute process-local TTL cache. Cache hits never change evidence state.
- `routes/external_knowledge_api.py`: `GET /api/external-knowledge/sources` and
  rate-limited `POST /api/external-knowledge/search`.
- `frontend/src/components/ExternalKnowledgeLookup.jsx`: user-triggered source
  retrieval control inside the existing Task 15 medication profile card.

## Data and governance flow

1. User explicitly starts a source lookup for a medication name.
2. The API validates the name and allowed source identifiers.
3. Fixed official API connectors fetch bounded JSON using the existing
   `MedicalSourceClient`.
4. The original response is ingested into the existing staging store.
5. API/UI return source metadata and evidence record IDs with
   `pending_clinical_review` and `staged_only` states.
6. A reviewer uses the existing review workflow. Accepted evidence remains
   staged and must still be curated, clinically approved, included in a
   reviewed release, and explicitly promoted.
7. Only the existing integrity-verified active release can populate approved
   Task 15 clinical profile sections.

The external lookup endpoint does not create clinical assertions, candidate
rules, reviewer decisions, releases, or patient-specific recommendations.

## Source coverage and limitations

| Source | Current integration | Jurisdiction | Limitation |
|---|---|---|---|
| RxNorm / RxNav | Existing identity search staged through adapter | US | Terminology identity, not clinical monograph |
| DailyMed | Existing SPL search staged through adapter | US | Search metadata is not a full label appraisal |
| openFDA | Existing drug-label search staged through adapter | US | Submitted labeling; applicability and accuracy require review |
| MedlinePlus Connect | RxCUI reference URL helper | US | Link/reference only; no content copied or redistributed |
| CDSCO / India | Capability scaffold only | India | No approved machine-readable source/API configured; no scraping |

DailyMed search currently stages SPL search responses. Retrieval and parsing of
individual SPL label documents, extraction into all 13 Task 15 profile sections,
and formulation-level applicability assessment are not yet implemented.

## Caching and operations

The first increment uses a per-process in-memory TTL cache (15 minutes). It
reduces repeated calls within a worker but is not shared across Gunicorn
workers and is cleared on restart. `refresh: true` bypasses the cache. Evidence
staging remains content-addressed and idempotent. A shared persistent cache is
not yet implemented.

## Security

- No user-supplied URL or host is accepted.
- Existing source client uses fixed HTTPS endpoints, finite timeouts, disabled
  redirects, bounded response sizes and JSON object validation.
- Search route is rate-limited to 5 requests/minute.
- External response exceptions are sanitized before reaching clients.
- CDSCO domains are added to the evidence URL allowlist for future manual
  ingestion, not as permission to scrape arbitrary pages.
- Source content remains untrusted and review-only.

## Next implementation increments

1. Fetch individual DailyMed SPL documents and preserve set ID/version/product
   identifiers; add explicit formulation and jurisdiction match assessment.
2. Add deterministic, locator-preserving extraction previews for openFDA and
   DailyMed label sections. Previews remain evidence excerpts, never assertions.
3. Bind extracted section candidates to existing Task 15 domain identifiers
   and Task 11 curation workflow, with human review and conflict checks.
4. Evaluate official Indian sources and terms. Implement a connector only when
   a documented, authorized machine-readable interface or permitted source
   acquisition process is established.
5. Add persistent shared caching if deployment scale requires it.
6. Extend frontend review-queue visibility without exposing unapproved content
   as approved clinical findings.

## DailyMed SPL extraction and review previews

The DailyMed connector retrieves a bounded set of individual SPL XML documents
using SET IDs obtained from the fixed DailyMed search endpoint. XML parsing
retains section codes, titles and verbatim text. The complete XML text is also
included in the normalized evidence payload; the ingestion envelope hashes the
retrieved JSON document and its normalized payload.

`services.dailymed_mapping` classifies only a small, explicit set of known SPL
section codes/titles into existing Task 15 domain identifiers. This is a
routing preview, not clinical interpretation. It does not transform excerpts
into validated candidate fields, because dosage, indication, contraindication
and precaution statements require human structuring and applicability review.
Unknown or ambiguous sections remain unmapped. `preview_staged_dailymed_evidence`
first verifies the evidence hashes and source metadata through the existing
review service, then returns locator-preserving previews. It does not modify
the evidence record or reviewer ledger.
