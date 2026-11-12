# Task 06 — Stage 5 Final Acceptance Audit

**Snapshot:** Task 06 Stage 5, based on the user-verified Stage 4 snapshot  
**Purpose:** consolidate the acceptance evidence for controlled knowledge curation, release publication, activation, rollback, and runtime loading.  
**Clinical status:** not clinically validated; not authorized for patient-care use.

## Acceptance checklist

| Area | Acceptance criterion | Evidence / disposition |
|---|---|---|
| Evidence intake | Source bytes and normalized payload are integrity checked; ingestion is review-only and idempotent. | Covered by `test_evidence_ingestion.py` and `test_evidence_review.py`; accepted evidence is still not runtime knowledge. |
| Evidence review | Reviewer decisions are append-only and evidence must be accepted for curation. | Covered by evidence-review and curation tests. |
| Candidate curation | Candidates are explicit, evidence-linked assertions; candidate author cannot approve their own candidate. | Covered by `test_knowledge_curation.py`; clinical decisions are distinct from source-evidence acceptance. |
| Release assembly | Only currently approved candidates with still-eligible evidence are included; creation does not activate. | Covered by `test_knowledge_release.py`. |
| Promotion | Only the configured steward/administrator role assertion can invoke promotion; evidence and approvals are rechecked. | Covered by release tests. Role strings are audit assertions, not authenticated identity. |
| Rollback | Only a previously completed promotion can be selected; runtime loads the restored release after a successful rollback. | Covered by successful rollback test. |
| Interrupted activation | An intent without a matching completion event is not accepted as active. | Covered by incomplete-promotion test and runtime audit verification. |
| Interrupted rollback | A pointer updated before its completion event is rejected by runtime. | Added in Stage 5 as `test_interrupted_rollback_fails_closed_until_completion_event`. |
| Audit integrity | Event hashes form a chain; tampered events and unbound pointers are rejected. | Covered by audit-chain, tampering, pointer-binding, and completion tests. |
| Release integrity | The manifest declares exactly the expected datasets and runtime rejects modified release content. | Covered by manifest and dataset tampering tests. |
| Runtime selection | Active-release mode uses the same verified release for interaction and food rules and never falls back to legacy datasets. | Covered by `test_knowledge_runtime.py` and release-loader tests. |
| API governance | No anonymous HTTP promotion or rollback endpoints are exposed. | Inspected `routes/api.py`; only read-only `GET /api/knowledge/status` is provided. Governance mutations remain CLI-only. |
| CLI boundary | CLI commands expose create/inspect/list/promote/rollback/status without claiming to authenticate the actor. | Inspected `scripts/manage_knowledge.py`; covered by CLI tests. Shell access must be restricted operationally. |
| Documentation | Test inventory and current verification history match the supplied project evidence. | README updated to 24 test modules and the user-reported Stage 5 full-suite result of 337 passed (Stage 4: 336 passed). |

## Verification record

### User-provided Windows verification of Stage 4

The user reported the following successful PowerShell results for the Stage 4 snapshot:

- Focused Stage 4 suite: **48 passed in 4.23 seconds**.
- Full suite: **336 passed in 17.39 seconds**.

The user then verified the Stage 5 snapshot on Windows:

- Focused governance/runtime suite: **58 passed in 7.63 seconds**.
- Full suite: **337 passed in 16.41 seconds**.
- Environment: Windows, Python 3.12; pytest-asyncio emitted a non-fatal fixture-loop deprecation warning.

### Stage 5 implementation-environment verification

The Stage 5 working environment used Python 3.13.5 and did not contain Flask or scikit-fuzzy. The attempted full-suite run stopped during collection with missing-dependency errors in API and reasoning-related modules. Installing the missing packages was not possible because package-index network access was unavailable.

A focused run of the release, curation, evidence, CLI, validation, and architecture-boundary modules reached **65 passed, 1 failed**. The one failure was the architecture-boundary subprocess test attempting to import `services.reasoning_service`, which imports the unavailable `skfuzzy` dependency. It did not expose a release-governance assertion failure. The focused release/curation/evidence/CLI tests passed in that run; Stage 5 adds an interrupted-rollback regression test that must be rerun in a fully provisioned environment.

The Stage 5 full-suite pass is user-verified. The implementation environment's dependency-blocked run remains a separate limitation and is not a replacement for that Windows verification.

```powershell
python -m pytest tests\test_knowledge_release.py tests\test_knowledge_curation.py tests\test_evidence_review.py tests\test_evidence_ingestion.py tests\test_knowledge_management_cli.py tests\test_knowledge_validation.py tests\test_knowledge_runtime.py -q
python -m pytest -q
```

## Operational and security limits

1. The SHA-256 event chain is tamper-evident, not a digital signature. A privileged actor able to rewrite the complete local log and release files can recompute hashes.
2. CLI actor IDs and roles are assertions written to the audit log. They are not proof of identity or authorization. Restrict host and shell access to authorized staff.
3. Promotion and rollback use local filesystem operations and are not a distributed transaction or multi-host lock. Serialize governance operations operationally.
4. If a process stops after writing an intent and replacing the active pointer but before appending the completion event, runtime rejects the pointer. Preserve the audit log and release files, investigate the interruption, and perform a documented, reviewed recovery. Do not hand-edit the pointer or audit log to bypass verification.
5. Legacy pre-Stage-4 audit logs without chain fields are rejected. Preserve backups and perform a reviewed migration before enabling active-release mode.
6. No existing medication rule is automatically approved or promoted. A governance release is not clinical validation, regulatory clearance, or permission to use RxLogic for patient care.

## Final disposition

The implementation contains the intended governance boundaries and regression coverage described above. Stage 5 has user-reported Windows verification (337 full-suite passes). This does not establish clinical validation or authorize patient-care use. Do not enable `RXLOGIC_KNOWLEDGE_MODE=active_release` in a clinical environment on the strength of software tests alone.
