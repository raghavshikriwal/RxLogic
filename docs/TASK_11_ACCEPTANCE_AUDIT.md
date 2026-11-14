# Task 11 — Acceptance Audit

**Audit scope:** release-level dual control, separation of duties, review-event integrity, promotion binding, rollback rationale, and fail-closed runtime loading.
**Clinical status:** not clinically validated; patient-care use remains prohibited.

## Acceptance criteria

| Criterion | Expected behavior |
|---|---|
| Versioned governance policy | Required review types, roles, quorum, separation rules, and security limits are explicit. |
| Manifest governance context | New releases bind release creator, candidate authors, and candidate-level clinical approvers. |
| Clinical release review | At least one `clinical_pharmacist` or `physician` reviewer approves the exact release manifest. |
| Governance release review | At least one `knowledge_steward` or `administrator` reviewer approves the exact release manifest. |
| Separation of duties | Reviewers differ from creator/authors/candidate approvers and from each other; promoter is a distinct identity. |
| Review audit integrity | Review events form a verified SHA-256 hash chain and bind to the raw manifest digest. |
| Promotion | Cannot occur until current dual reviews and candidate approval/evidence checks pass. |
| Runtime integrity | Active pointer, promotion chain, manifest/dataset hashes, and current review digest all verify. |
| Rollback | Requires an independent actor, non-empty rationale, previously completed promotion, current dual review, and still-eligible evidence. |
| Legacy compatibility | Old releases may be inspected but cannot bypass Task 11 governance to become active. |
| Clinical safety boundary | Clinical-use authorization remains false. |

## Automated coverage

- `tests/test_knowledge_release.py`: dual-review gate, review rejection, reviewer/promoter independence, review-log tampering, active-loader integrity, and rollback rationale/recovery behavior.
- `tests/test_knowledge_management_cli.py`: release-review command parsing and mandatory rollback rationale.
- `tests/test_task11_audit.py`: empty fail-closed baseline, policy validation, and review-log tampering.

## Acceptance commands (Windows PowerShell)

```powershell
python -m pytest tests\test_knowledge_release.py tests\test_knowledge_management_cli.py tests\test_clinical_knowledge.py tests\test_task11_audit.py -q
python -m scripts.audit_task11 --output reports\task11_acceptance_audit.json
python -m pytest -q
```

## Current implementation-side verification

- Focused release/CLI/clinical-knowledge/Task 11 audit suite: **46 passed**.
- Broader dependency-available regression subset: **307 passed**; test modules requiring unavailable `flask`, `psycopg2`, and `scikit-fuzzy` were excluded. This is not a full-suite result.
- Task 10 and Task 11 structural audits: passed; Task 11 audit found zero releases, zero review events, and no active release, which is the expected fail-closed baseline.
- Python compilation of changed Task 11 Python modules: passed.
- Full-suite collection was not completed in the implementation environment because `flask`, `psycopg2`, and `scikit-fuzzy` were unavailable. Final acceptance requires a full `python -m pytest -q` run in the fully provisioned Windows project environment.

## Explicit limitations

1. Reviewer IDs and role strings are entered through a local CLI and are not authenticated identities or credential checks.
2. SHA-256 hash chains detect accidental or partial tampering but are not digital signatures. A privileged actor with write access to all local files can rewrite and re-hash the chain.
3. Concurrent governance writes must be serialized operationally; local JSONL append operations are not a distributed transaction system.
4. No real clinical source record, clinical assertion, reviewer identity, or approval was fabricated for this task.
5. A valid governance release is not proof of clinical validity, regulatory clearance, or permission for patient-care use.
