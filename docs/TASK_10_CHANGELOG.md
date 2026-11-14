# Task 10 Changelog

## Initial implementation

- Added a strict clinical validation case schema and adjudication governance.
- Added binary performance metrics with explicit undefined-value handling.
- Added two-reviewer agreement and Cohen's kappa reporting.
- Added a Task 10 audit for fail-closed runtime behavior and dataset governance.
- Added an intentionally empty validation-case registry; no clinical facts or
  reference labels were fabricated.
- Added unit and audit tests plus the validation protocol.

## Explicit limitations

- No independent clinical validation has been performed.
- Reviewer identity and credentials are not authenticated by this local JSON
  schema; a trusted review workflow is required.
- Clinical performance metrics remain unavailable until independently
  adjudicated reference cases and versioned model predictions exist.
- Patient-care use remains prohibited.
