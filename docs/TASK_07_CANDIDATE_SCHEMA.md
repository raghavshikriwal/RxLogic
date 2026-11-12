# Task 07 candidate authoring reference

All candidate files are UTF-8 JSON objects. They are authored by a human, linked to one or more evidence record IDs already accepted for curation, and stored append-only. `rule_id`, `assertion_id`, evidence source IDs, review status, candidate status, and promotion status are assigned by the system and must not be supplied by the author.

## Candidate types and required fields

| `--type` | Required rule fields |
|---|---|
| `interaction_rule` | `medication_a`, `medication_b`, `severity`, `evidence`, `description`, `source` |
| `food_rule` | `medication`, `requirement`, `note`, `source` |
| `drug_food_interaction` | `medication`, `food_or_component`, `clinical_effect`, `severity`, `evidence_strength`, `source` |
| `contraindication` | `medication`, `condition_or_population`, `clinical_action`, `evidence_strength`, `source` |
| `dosage_reference` | `medication`, `indication`, `population`, `dose_text`, `route`, `frequency`, `evidence_strength`, `source` |
| `administration_instruction` | `medication`, `instruction`, `evidence_strength`, `source` |

## Common optional appraisal fields

- `jurisdiction`: defaults to `unspecified`; use the actual source jurisdiction.
- `applicability_notes`: scope limitations such as formulation, population, indication, or route.
- `source_quality_tier`: `high`, `moderate`, `low`, or `not_assessed` (default). If assessed, `source_quality_rationale` is mandatory.
- `evidence_direction`: `supports`, `contradicts`, `qualifies`, or `unknown` (default).
- `conflict_status`: `not_assessed`, `no_known_conflict`, `conflicting_evidence`, or `resolved` (default).
- `conflict_resolution`: mandatory when `conflict_status` is `resolved`.

Task 07 candidates cannot receive clinical approval until conflict status is explicitly `no_known_conflict` or `resolved`. An assertion with unresolved conflicting evidence must not be promoted. The approval record is independent of the author; candidate authors cannot approve their own work.

## Dosage-specific restriction

A dosage reference must include a source-scoped indication, population, route, frequency, and textual dose reference. The system sets `patient_specific` to `false`; authors cannot override this. The reference is not used to calculate a dose for an individual and must not be presented as a prescription.

## CLI

```powershell
python -m scripts.manage_knowledge candidate-create --type dosage_reference --rule-file .\\dosage-reference.json --evidence-id EVD-... --author-id author-1 --rationale "Human-authored source mapping"
python -m scripts.manage_knowledge candidates
python -m scripts.manage_knowledge candidate-decide KNC-... --decision approved --reviewer-id reviewer-1 --reviewer-role clinical_pharmacist --rationale "Independent review"
```

Evidence IDs may be repeated as separate `--evidence-id` arguments. Every evidence record is rechecked when the candidate is created, clinically reviewed, assembled into a release, and promoted. A later evidence-review decision or hash mismatch invalidates the candidate's release path.
