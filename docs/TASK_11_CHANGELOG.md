# Task 11 Changelog — Release Governance and Dual Control

## Implemented in this branch

- Added a versioned `knowledge/release_governance_policy.json` policy describing required review roles, minimum approvals, separation of duties, rollback rationale, and the local identity/authentication boundary; the policy file is included as a hash-bound dataset in each new release.
- Extended new immutable release manifests with Task 11 governance context: release creator, candidate authors, and candidate-level clinical approvers.
- Added release-level clinical and governance review types with role checks, rationale requirements, and case-insensitive identity separation.
- Added `knowledge/release_review_events.jsonl` as an append-only SHA-256 hash-chained review log bound to exact raw release-manifest hashes.
- Required at least one current clinical release approval and one distinct governance release approval before promotion.
- Required the promoter to be independent of the release creator, candidate authors, candidate-level clinical approvers, and release reviewers.
- Bound the active pointer and promotion/rollback audit events to the release-specific review digest; the runtime loader re-verifies this digest.
- Prevented release review changes after activation.
- Required a non-empty rationale for rollback and revalidated candidate approval/evidence eligibility plus dual release reviews before rollback.
- Added `release-review` and `review-status` knowledge-management CLI commands.
- Added Task 11 policy/release-governance audit service and CLI.
- Added regression tests for dual approval, rejection handling, separation of duties, hash-chain tampering, active-loader enforcement, and rollback rationale.
- Kept `clinical_use_permitted` false and did not fabricate clinical data, reviewer identities, credentials, or approvals.

## Compatibility and migration

Older Task 06–10 release bundles remain inspectable if their current integrity checks pass. They do not contain Task 11 governance context and are intentionally not eligible for new promotion, rollback, or active runtime loading. Rebuild eligible releases through the current workflow; do not manually edit old manifests or pointers.

## Verification in the implementation environment

- Focused release, knowledge CLI, clinical-knowledge integration, and Task 11 audit tests: **46 passed**.
- Broader dependency-available regression subset: **307 passed**; modules requiring unavailable `flask`, `psycopg2`, and `scikit-fuzzy` were excluded, so this is not a full-suite result.
- Task 10 and Task 11 structural audits: passed; Task 11 audit found zero releases, zero review events, and no active release (expected fail-closed baseline).
- Python compilation of the changed release service, audit service, and CLI: passed.
- Full project regression suite: not completed in the implementation environment because `flask`, `psycopg2`, and `scikit-fuzzy` were unavailable during collection. Run it in the fully provisioned Windows environment before final acceptance.

## Limitations

- CLI reviewer IDs/roles are not authenticated and credentials are not verified.
- SHA-256 hash chains are tamper-evident, not digital signatures or external trust anchors.
- Local JSONL writes require operational serialization; no distributed locking is provided.
- These controls are software governance evidence, not clinical correctness or patient-care authorization.
