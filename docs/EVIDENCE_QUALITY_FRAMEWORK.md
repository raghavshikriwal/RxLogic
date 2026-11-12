# Evidence quality, certainty, and applicability framework

This framework defines the separate dimensions preserved by RxLogic. It is a governance aid, not a formal GRADE assessment and not a clinical validation protocol.

## Keep the dimensions separate

| Dimension | Question | Values |
|---|---|---|
| Source verification | Is the captured source record traceable and integrity-checked? | `unverified`, `verified`, `integrity_verified_clinical_review_recorded` |
| Source quality | How authoritative and methodologically reliable is this source for this assertion? | `high`, `moderate`, `low`, `not_assessed` |
| Assertion evidence strength | How strongly does the total evidence support this specific assertion? | `strong`, `moderate`, `limited`, `unknown` |
| Clinical severity | How serious is the potential outcome if the assertion applies? | `mild`, `moderate`, `severe`, `unknown` |
| Evidence direction | How does a source relate to the assertion? | `supports`, `contradicts`, `qualifies`, `unknown` |
| Conflict status | Have conflicting sources or findings been assessed? | `not_assessed`, `no_known_conflict`, `conflicting_evidence`, `resolved` |
| Applicability | To whom/product/use does the assertion apply? | jurisdiction, population, indication, formulation, route, dose range, date/version |

A SHA-256 match demonstrates byte integrity relative to a recorded digest; it does not establish publisher authority, methodological quality, clinical truth, or applicability. An official label may be authoritative for its approved jurisdiction and product while not automatically generalizing to another formulation or jurisdiction.

## Source-quality rubric

The candidate author proposes the source-quality value and rationale; an independent physician or clinical pharmacist reviews the complete candidate (including this appraisal) before the value can enter a release:

- `high`: authoritative regulator-approved labeling or a recognized evidence synthesis/guideline directly applicable to the assertion, with a stable locator and identifiable version/date.
- `moderate`: well-conducted primary research or a recognized professional reference with identifiable methods/version, but with limitations in directness or generalizability.
- `low`: indirect, limited, methodologically weak, outdated, or poorly applicable material.
- `not_assessed`: insufficient metadata or no documented quality appraisal.

An assessed value requires a written rationale. Do not infer quality solely from publisher name or source type. These labels are project governance values, not a replacement for GRADE or formal systematic review.

## Assertion evidence strength

`strong`, `moderate`, `limited`, and `unknown` describe evidence supporting one assertion, not the source itself. A high-quality source may provide limited evidence for a particular population; several moderate-quality sources may collectively support a stronger conclusion. Preserve disagreements and applicability limits rather than averaging them into false certainty.

## Conflict handling

- `not_assessed`: no explicit conflict assessment has been recorded.
- `no_known_conflict`: a reviewer assessed the cited evidence set and found no unresolved conflict within the stated scope.
- `conflicting_evidence`: material evidence differs in direction or applicability; the assertion must remain visibly conflicted.
- `resolved`: a reviewer documented how the conflict was reconciled and the scope/limitations of that resolution.

Task 07 clinical assertion candidates cannot be approved while conflict status is `not_assessed` or `conflicting_evidence`. `resolved` requires a resolution rationale. This is a workflow gate, not proof that the conflict was correctly adjudicated.

## Applicability and provenance

Future assertions should identify exact publisher, document title/version, publication or label revision date, canonical URL or stable locator, retrieval date, jurisdiction, product/ingredient, formulation, route, indication, and population where relevant. Keep supporting and contradicting source IDs linked to the assertion. Missing metadata remains missing; it must not be synthesized.

## Safety interpretation

Coverage gaps are `not_evaluated`, not negative findings. Dosage records are source references only, not patient-specific prescriptions. Clinical approval in the local governance workflow does not establish regulatory compliance, clinical validation, or authorization for patient care.
