# Task 08 — Medication identity expansion and evidence coverage controls

**Status:** implementation snapshot; Windows acceptance required.
**Audit class:** structural, terminology, and governance checks only. Not clinical validation.

## Delivered

- Added a versioned medication identity catalog with canonical ingredient names, RxCUIs, and explicit aliases.
- Expanded the development medication map from 10 to 11 entries by registering **acetaminophen (RxCUI 161)** and the common name **paracetamol** as an alias.
- Updated the name-normalization path so the new catalog alias resolves to the canonical ingredient before coverage checks. The medication form can now recognize `paracetamol` as `acetaminophen`.
- Added catalog schema validation, uniqueness checks for canonical names/RxCUIs/aliases, HTTPS identity-source checks, and exact consistency checks against the runtime medication map.
- Added a medication-catalog audit CLI and Task 08 acceptance audit.
- Included the medication catalog in newly assembled immutable releases. Task 06 and Task 07 releases without this dataset remain readable; Task 08 releases bind the catalog in their manifest hashes and validate it at load time.
- Fixed a Task 07 audit vacuity: an empty clinical assertion collection is no longer described as if there were approved clinical assertions. The audit now reports record presence and unapproved-record status separately.
- Updated coverage tests and baseline denominator: 11 medications produce 55 unordered drug pairs.

## What did not change

No new drug–drug interaction, drug–food interaction, contraindication, dosage, or administration claim was fabricated or promoted for acetaminophen. Its identity is registered, but its clinical evidence coverage remains **not evaluated**. The 12 legacy DDI rules and four legacy food rules remain unreviewed. Absence of a rule is not evidence of safety.

## Expected development coverage after Task 08

- Medication identities: 11.
- Possible unordered medication pairs: 55.
- DDI assertions present but unreviewed: 12.
- DDI pairs not evaluated: 43.
- Legacy meal-guidance entries present but unreviewed: 4.
- Medications without a meal-guidance entry: 7.
- New approved clinical assertions for food interactions, contraindications, dosage references, and administration instructions: 0.

These are inventory counts for a small development fixture, not a comprehensive formulary or clinical performance measure.

## Acceptance commands (Windows PowerShell)

```powershell
python -m pytest tests\test_medication_catalog.py tests\test_name_normalizer.py tests\test_knowledge_coverage.py tests\test_knowledge_validation.py tests\test_knowledge_release.py tests\test_clinical_knowledge.py -q
python -m pytest -q
python -m services.knowledge_validation
python -m scripts.audit_medication_catalog --output reports\medication_catalog_audit.json
python -m scripts.audit_knowledge_coverage --output reports\knowledge_coverage.json
python -m scripts.audit_task07 --output reports\task07_acceptance_audit.json
python -m scripts.audit_task08 --output reports\task08_acceptance_audit.json
```

## Identity reference

- RxNorm concept 161 identifies acetaminophen: <https://purl.bioontology.org/ontology/RXNORM/161>.
- NLM's RxNorm release note documents the ingredient concept identifier 161: <https://www.nlm.nih.gov/pubs/techbull/mj20/brief/mj20_rxnorm_may_2020_release.html>.

## Implementation-side verification

- Task 08 focused suite: **80 passed**.
- Broader regression subset: **279 passed**.
- Python compilation, knowledge structural validation, medication catalog audit, coverage report, Task 07 audit, and Task 08 audit: passed.
- Full-suite collection is blocked in the implementation environment because Flask and scikit-fuzzy are not installed and package installation is unavailable. The full Windows suite must be run before final acceptance; API integration and frontend build therefore remain user-side verification items.

## Safety and release boundary

`clinical_use_permitted` remains `false`. Catalog membership means identity recognition only. New immutable releases include the validated catalog as a hash-bound dataset; no release or catalog audit authorizes patient-care use. Clinical assertions still require verified evidence ingestion, independent physician/clinical-pharmacist approval, and controlled promotion. Dosage references remain non-patient-specific.
