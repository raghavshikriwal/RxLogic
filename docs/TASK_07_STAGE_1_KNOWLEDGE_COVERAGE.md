# Task 07 — Knowledge coverage baseline

The Stage 1 inventory is retained as the starting baseline for the complete Task 07 implementation. It records all 45 unordered medication pairs in the ten-medication development map: 12 have legacy assertions and 33 are not evaluated. Four medications have legacy meal-timing rules and six have no recorded meal-timing assessment. Contraindications, dosage references, administration instructions, and drug–food component interactions had no governed assertions at baseline.

These are data-inventory counts only. Legacy assertions remain `needs_clinical_review`; legacy source labels are unverified and their source quality is `not_assessed`. No new clinical claims are invented to fill coverage gaps.

Run the deterministic report:

```powershell
python -m scripts.audit_knowledge_coverage
python -m scripts.audit_knowledge_coverage --output reports\knowledge_coverage.json
```

A missing assertion means `not_evaluated`, never “no interaction”, “no contraindication”, or “safe”. Drug–food component coverage is medication-level until a governed food/component denominator is available.
