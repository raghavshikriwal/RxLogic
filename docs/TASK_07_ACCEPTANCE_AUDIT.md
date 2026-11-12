# Task 07 — Implementation and governance acceptance audit

**Scope:** typed knowledge expansion, evidence appraisal, conflict handling, coverage accounting, and controlled release integration.  
**Audit type:** software structure and governance controls; not clinical validation.  
**Clinical-use status:** prohibited (`clinical_use_permitted: false`).

## Implemented

- New governed assertion families: drug–food/component interactions, contraindications, dosage references, and administration instructions.
- Existing drug–drug interaction and meal-timing candidate types remain supported.
- Candidate creation requires accepted evidence and rechecks source-response, normalized-payload, and source-metadata hashes at creation, clinical decision, release assembly, and promotion.
- Independent physician/clinical-pharmacist review remains required; candidate authors cannot approve their own candidates.
- Task 07 assertions cannot be approved until conflict status is explicitly `no_known_conflict` or `resolved`; resolved conflicts require a written rationale.
- Source-quality values are separate from assertion evidence strength and clinical severity. An assessed source-quality value requires a rationale and is linked to the independent clinical approval decision in the release provenance record.
- Evidence direction and applicability notes are preserved. Legacy source labels remain unverified and source quality remains not assessed.
- Immutable releases include `clinical_assertions.json`; release manifests bind its hash. Runtime verifies the schema, approved status, conflict assessment, evidence-source links, and provenance digests. Legacy Task 06 three-dataset releases remain loadable and receive an empty Task 07 assertion bundle.
- The active-release loader returns the governed clinical assertion dataset. Existing patient-plan reasoning does not consume new contraindication, dosage, or administration records.
- Dosage references are explicitly non-patient-specific. No patient-specific dose calculation or prescribing behavior is introduced.
- Coverage reporting exposes missing knowledge without interpreting absence as safety. Drug–food component reporting is medication-level until a governed component taxonomy exists.
- A deterministic audit CLI writes `reports/task07_acceptance_audit.json`.

## Intentionally not added

No new medical facts have been fabricated to make the coverage percentages look better. The current development dataset retains 12 legacy DDI assertions and four legacy meal-timing assertions; all remain `needs_clinical_review`. The new clinical assertion arrays are empty until real source documents have been ingested, accepted through evidence review, mapped by a human author, and independently approved by a qualified clinical reviewer. Empty arrays mean not evaluated, not no risk.

## Automated checks performed in the implementation environment

- Task 07, evidence, and governance focused suite: **76 passed**.
- Broader available regression subset: **272 passed** when excluding modules whose imports require unavailable `Flask` and `scikit-fuzzy` dependencies, plus the architecture-boundary module whose subprocess imports `scikit-fuzzy`.
- Python compilation: passed.
- `python -m services.knowledge_validation`: passed; structural validation only.
- `python -m scripts.audit_task07 --output reports/task07_acceptance_audit.json`: passed; structural/governance audit only.
- `python -m scripts.audit_knowledge_coverage --output reports/knowledge_coverage.json`: passed.

The full `pytest -q` attempt could not collect five modules because this implementation environment lacks `Flask` and `scikit-fuzzy`. One architecture-boundary subprocess test also requires `scikit-fuzzy`; it was excluded from the 272-test subset. This is an environment dependency limitation, not evidence that those modules pass. The user's Windows environment has these dependencies and must run the full suite before final acceptance.

## Remaining risks and boundaries

1. Local CLI actor IDs and roles are audit assertions, not authenticated identities. Restrict host and shell access to authorized staff.
2. The local SHA-256 audit chain is tamper-evident, not a digital signature or external trust anchor.
3. Clinical correctness, completeness, source applicability, and reviewer competence are outside structural software validation.
4. The ten-medication list is a small development fixture, not a comprehensive formulary. The 45-pair denominator applies only to that fixture.
5. Drug–food component coverage lacks a complete controlled ingredient/component denominator.
6. The new contraindication, dosage, and administration data are not yet integrated into patient-plan recommendations; this is intentionally deferred until clinical validation and a separate safety review.
7. Do not enable clinical use or treat promotion as regulatory clearance.

## Windows acceptance commands

```powershell
python -m pytest tests\test_clinical_knowledge.py tests\test_knowledge_coverage.py tests\test_knowledge_curation.py tests\test_knowledge_release.py tests\test_knowledge_validation.py tests\test_knowledge_management_cli.py -q
python -m pytest -q
python -m services.knowledge_validation
python -m scripts.audit_knowledge_coverage --output reports\knowledge_coverage.json
python -m scripts.audit_task07 --output reports\task07_acceptance_audit.json
```
