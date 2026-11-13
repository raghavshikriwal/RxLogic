# Task 09 API contract additions

Both `POST /api/plan` and `POST /api/plan/nl` accept an optional context object:

```json
{
  "patient_context": {
    "foods": ["grapefruit"],
    "conditions": ["pregnancy"]
  }
}
```

Each field is an array of at most 50 non-empty strings, each no longer than
120 characters. Matching is exact and case-insensitive. No patient condition
is inferred from natural-language medication descriptions. The context and
context-derived findings are not written to plan history.

The response adds `clinical_assessment` with:

- `status`, `findings`, and per-domain availability/status counts;
- `unresolved_conflicts` and excluded-assertion counts;
- `dosage_safety`, which explicitly states no patient-specific dose is generated;
- `interpretation` and `clinical_use_permitted: false`.

A `no_matching_approved_assertion` result is not a negative clinical finding.
The response explicitly warns that missing or conflicting evidence is not
proof of safety. Dosage references are never serialized as dose instructions.
