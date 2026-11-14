# Task 10 — Clinical Validation & Reliability Protocol

## Purpose

Task 10 establishes a reproducible framework for independently adjudicated
clinical reference cases and verifies fail-closed software behavior. It does
not create clinical knowledge, certify the system, or authorize patient care.

## Two separate evidence tracks

1. **Software invariant testing** checks deterministic system properties such
   as missing knowledge not being represented as safety, unapproved assertions
   not being emitted, and patient-specific dosing not being generated. These
   tests are engineering evidence only.
2. **Clinical reference evaluation** requires real, traceable source material,
   two independent qualified reviewers, and an independent adjudicator when
   required. No reference labels are included by default.

Never combine the two tracks into one clinical accuracy score.

## Dataset contract

`knowledge/clinical_validation_cases.json` is the versioned case registry.
Each clinical reference case must contain a unique case ID, domain, scenario,
non-identifying input context, two independent reviewer decisions, source IDs,
and an independent adjudication record. Reviewer role fields are declarations,
not credential authentication. Production review must occur in an authenticated
workflow outside this JSON file. Do not place patient identifiers, dates of
birth, contact details, medical record numbers, or free-text patient histories
in this dataset.

Allowed reference outcomes are `finding_present` and
`insufficient_approved_knowledge`. The latter must never be interpreted as
"safe" or "no interaction". Unadjudicated cases must have no reference label.

## Metrics

The evaluator reports confusion matrix, accuracy, precision, sensitivity,
specificity, and F1 for the positive class `finding_present`. Undefined
zero-denominator metrics are `null`, not zero. Reviewer agreement reports raw
agreement and Cohen's kappa; kappa is `null` when mathematically undefined.
Metrics are computed only from adjudicated reference cases and versioned
predictions. They describe agreement with that dataset, not clinical safety,
generalizability, or fitness for patient care.

## Run the audit

```powershell
python -m scripts.audit_task10 --output reports/task10_acceptance_audit.json
pytest tests/test_clinical_validation.py tests/test_task10_audit.py -q
pytest -q
```

## Acceptance criteria

- Validation dataset is structurally valid and contains no fabricated labels.
- Adjudicated cases require two distinct reviewers and an independent
  adjudicator with traceable evidence IDs and rationale.
- Unadjudicated cases cannot contribute to performance metrics.
- Metrics reject missing/invalid labels and expose undefined denominators.
- Runtime probes confirm empty/unapproved knowledge fails closed.
- Patient-specific dosing remains disabled and `clinical_use_permitted` remains
  false.
- Audit output explicitly reports `not_performed` when there are no adjudicated
  clinical reference cases.

## Current baseline

The supplied development dataset is intentionally empty. Therefore clinical
performance is **not evaluated**. A passing Task 10 software audit is not a
clinical validation result and does not imply approval for patient care.
