# Task 09 — Clinical Reasoning Integration

## Scope

Task 09 connects the governed Task 07/08 clinical assertion dataset to the
reasoning response. It does not add or fabricate clinical assertions and does
not establish clinical validation.

## Implemented

- Added `ClinicalReasoningEngine`, which accepts the active release assertion
  bundle or the development assertion dataset.
- The mutable legacy/development assertion JSON is never a runtime clinical
  authority; only the integrity-verified active release supplies runtime assertions.
- Runtime findings are emitted only for records that are explicitly
  `clinically_approved`, have `no_known_conflict` or `resolved` conflict state,
  and carry at least one evidence-source ID.
- Pending, unreviewed, rejected, withdrawn, conflict-unassessed, and
  conflicting-evidence records are excluded. Unresolved conflicts are surfaced
  as exclusions, not converted into warnings or recommendations.
- Drug/food assertions require an explicit matching food context. Contra-
  indication assertions require an explicit matching condition context.
  Context is exact, case-insensitive matching; no diagnosis or inference is
  performed.
- Approved administration assertions can be returned with assertion ID,
  evidence strength, source IDs, source, jurisdiction, and review status.
- Dosage references are counted for transparency but never returned as dose
  instructions. The API explicitly reports that no patient-specific dosing is
  generated.
- Added a clinical assessment to `/api/plan` and `/api/plan/nl` responses.
  Optional `patient_context.foods` and `patient_context.conditions` are validated
  and are not included in PlanLog history records.
- Added a frontend panel showing domain coverage, approved findings, excluded
  conflicts, evidence provenance, and non-prescriptive limitations.
- Added unit tests for context matching, evidence governance, conflict
  exclusion, empty-knowledge behavior, and dosage non-prescription guarantees.

## Current knowledge limitation

The Task 08 `clinical_assertions.json` dataset contains zero records in all four
clinical assertion domains. Therefore the new runtime correctly reports that
approved clinical assertion knowledge is currently unavailable; it does not
create clinical findings from legacy unreviewed rules. This is an integration
milestone, not a claim of expanded clinically approved knowledge.

## Safety boundary

RxLogic remains an educational software demonstrator. It is not clinically
validated and must not be used to diagnose, prescribe, alter medication doses,
or make patient-care decisions. All assertions require trustworthy provenance
and independent qualified clinical review before release promotion.
