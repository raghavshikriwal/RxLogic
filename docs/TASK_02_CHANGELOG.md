# Task 02 Changelog

## Added

- `knowledge/manifest.json` — release identity, dataset versions, and explicit development/unreviewed publication status.
- `knowledge/evidence_sources.json` — source records linked by stable IDs. Legacy free-text labels are explicitly marked unverified; no citations were invented.
- `services/knowledge_validation.py` — offline validation of release consistency, stable IDs, duplicate pairs, medication references, review states, and evidence-source links.
- `tests/test_knowledge_validation.py` — regression tests for the migrated knowledge release.

## Changed

- Migrated all existing interaction and food rules to schema version 2.0.0.
- Added stable IDs to existing rules and evidence-source references.
- Marked all migrated assertions `needs_clinical_review`.
- Updated the interaction rule loader to prefer stored stable IDs while retaining generated IDs for legacy/test fixtures.
- Extended food-rule records to retain stable IDs, evidence-source references, and review status.

## Preserved

- No new medication, interaction, or food assertion was added.
- Existing rule descriptions, severity labels, evidence labels, RxCUIs, aliases, and scheduling constraints were retained.
- Existing legacy rule-file fixtures remain supported.

## Validation boundary

Structural validation does not verify clinical correctness. Legacy source labels do not identify exact publications, label sections, dates, or jurisdictions. All migrated assertions remain unreviewed and the release is not approved for clinical use.
