# Task 07 — Clinical knowledge expansion and evidence governance

## Scope delivered

Task 07 expands the governed knowledge model beyond the original drug–drug and meal-timing rules. It adds typed, evidence-linked assertion families for:

- Drug–food/component interactions (distinct from simple with-food/empty-stomach meal timing).
- Contraindications and clinically relevant condition/population restrictions.
- Source-backed dosage references, scoped to an indication, population, route, and frequency.
- Administration instructions.

The release format also records source-quality appraisal, assertion evidence strength, evidence direction, jurisdiction/applicability notes, and conflict status/resolution. These dimensions are deliberately separate from interaction severity and source-byte integrity.

## Governance and safety controls

1. New assertions require evidence records currently accepted for curation, with source-byte, normalized-payload, and canonical source-metadata hashes revalidated. Duplicate response bytes cannot silently replace the publisher/title/jurisdiction/URL metadata.
2. Candidate creation is append-only and does not modify runtime datasets.
3. Clinical approval must be recorded by a physician or clinical pharmacist who is not the candidate author.
4. Task 07 assertion families require an explicit conflict assessment (`no_known_conflict` or `resolved`) before approval. A resolved conflict requires a written resolution rationale.
5. An assessed source-quality value (`high`, `moderate`, or `low`) requires a rationale and is carried into the release with the independent clinical reviewer decision that approved the candidate. `not_assessed` remains the default.
6. Release creation includes only currently approved candidates and produces a new `clinical_assertions.json` dataset. Creation does not activate it.
7. Promotion revalidates approval/evidence and is recorded in the existing tamper-evident audit chain. Runtime verifies every dataset hash and clinical-assertion schema.
8. Dosage references are non-patient-specific source summaries. They are not prescriptions, dose calculators, or patient-specific recommendations.

## CLI workflow

Stage evidence using the existing `scripts.ingest_evidence` workflow, inspect and accept it using `scripts.review_evidence`, then create a JSON rule file and candidate:

```powershell
python -m scripts.manage_knowledge candidate-create --type contraindication --rule-file .\candidate.json --evidence-id EVD-... --author-id knowledge-author --rationale "Human-authored rationale"
python -m scripts.manage_knowledge candidates
python -m scripts.manage_knowledge candidate-decide KNC-... --decision approved --reviewer-id pharmacist-1 --reviewer-role clinical_pharmacist --rationale "Independent clinical review rationale"
python -m scripts.manage_knowledge create KNC-... --actor-id steward-1 --rationale "Release rationale"
python -m scripts.manage_knowledge promote RXK-... --actor-id steward-1 --actor-role knowledge_steward
python -m scripts.manage_knowledge status
```

Candidate rule schemas are enforced by `services.knowledge_curation`. The exact required fields are covered by `tests/test_clinical_knowledge.py`. For Task 07 types, include `conflict_status: no_known_conflict` or `conflict_status: resolved`; when resolved, include `conflict_resolution`. If setting `source_quality_tier` to `high`, `moderate`, or `low`, include `source_quality_rationale`.

## Coverage report

```powershell
python -m scripts.audit_knowledge_coverage
python -m scripts.audit_knowledge_coverage --output reports\knowledge_coverage.json
python -m services.knowledge_validation
python -m scripts.audit_task07 --output reports\task07_acceptance_audit.json
```

Coverage distinguishes unreviewed, approved, conflicting, and not-evaluated records. No assertion for a medication/domain means not evaluated; it does not mean no risk or safe use. Drug–food component interactions are reported at medication-level until a governed food/component taxonomy is established.

## Runtime boundary

The active-release loader verifies and returns the new clinical assertion dataset as governed knowledge. Existing patient-plan reasoning does not yet consume the new contraindication, dosage-reference, or administration datasets to generate recommendations. This is intentional: a structurally valid and approved governance record is not evidence of clinical validation, and no new dose calculation or automated contraindication decision is enabled by this task.

`clinical_use_permitted` remains `false`. RxLogic remains an educational software demonstrator, not a clinically validated decision-support system.

## Verification record

Implementation-side verification:

- Task 07, evidence, and governance focused suite: **76 passed**.
- Broader available regression subset: **272 passed** with the dependency-blocked modules and the architecture-boundary subprocess module excluded.
- Python compilation, structural validation, coverage report generation, and Task 07 structural/governance audit: passed.
- The full suite cannot be collected in this implementation environment because Flask and scikit-fuzzy are unavailable. The complete Windows suite must be run before final acceptance.
