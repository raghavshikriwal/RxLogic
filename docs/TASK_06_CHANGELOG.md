# Task 06 — Controlled knowledge curation and promotion

## Status

**Stage 1 implemented in the working snapshot; not yet a completed Task 06 release.**

## Stage 1 scope

- Adds `services/knowledge_curation.py` for explicit, human-authored interaction-rule and food-rule candidates.
- Candidate creation requires one or more evidence records whose latest Task 05 decision is `accepted_for_curation`.
- Re-inspects each evidence record and verifies original source bytes, normalized payload, and the hashes recorded by the latest evidence-review decision.
- Stores candidates in an append-only `knowledge/curation/candidates.jsonl` ledger, separate from active runtime datasets.
- Stores clinical decisions in a separate append-only `candidate_decisions.jsonl` ledger.
- Restricts clinical approval/rejection to `clinical_pharmacist` and `physician` roles and prohibits candidate self-approval.
- Records a digest of the candidate reviewed by the clinician.
- Approval is not promotion. Candidate status remains separate from publication status, which remains `not_promoted`.
- No runtime loader, active manifest, interaction dataset, or food dataset is changed in this stage.

## Explicitly deferred to later Task 06 stages

- Candidate revision/supersession workflow.
- Full semantic validation against medication terminology and dataset-specific constraints.
- Immutable release assembly and manifest activation.
- Runtime loading exclusively from approved releases.
- Promotion authorization, atomic activation, release history, and rollback.
- CLI commands, API integration, audit export, and full operational documentation.

## Tests

`tests/test_knowledge_curation.py` covers accepted-evidence gating, revalidation/hash binding, invalid rule fields, independent clinical approval, append-only decision behavior, and the invariant that candidate work does not modify runtime knowledge files.

Run from the project root:

```powershell
python -m pytest tests/test_knowledge_curation.py -q
```

## Safety boundary

This workflow is governance infrastructure, not clinical validation. Test fixtures and candidate records are not clinical recommendations. No candidate becomes active knowledge in Stage 1.

## Stage 2 — Immutable releases, explicit promotion, and approved runtime loader

**Status:** implementation complete in this snapshot; Windows verification pending.

### Added

- `services/knowledge_release.py` assembles immutable release directories from explicitly selected candidates only when each candidate has a current independent clinical approval and its accepted evidence still passes Task 05 integrity/review checks.
- Release datasets are generated from approved candidates. The legacy interaction dataset contributes medication-to-RxCUI terminology coverage only; its unreviewed interaction assertions are never copied into a release.
- Release manifests record candidate IDs, clinical decision IDs, dataset SHA-256 digests, creator, rationale, and a policy that disallows unreviewed runtime records and clinical-use claims.
- Building a release does **not** activate it. A separate promotion action requires `knowledge_steward` or `administrator`, revalidates candidate approval and evidence at activation time, writes an atomic active-release pointer, and appends an audit event.
- Rollback can point only to a previously promoted, integrity-valid release. Promotion/rollback events are append-only.
- The active pointer pins the manifest SHA-256; the manifest pins each dataset SHA-256. The runtime loader fails closed if there is no active release, if the pointer/manifest/datasets are inconsistent, or if the release policy permits unreviewed records.
- `RuleEngine.from_active_release(...)` and `FoodRules.from_active_release(...)` load only through the fail-closed approved-release loader. They do not fall back to legacy development datasets.
- Release content remains marked `clinical_use_permitted: false`. A recorded clinical review is a governance approval step, not proof of clinical validity or regulatory authorization.

### Runtime cutover boundary

The existing default constructors (`RuleEngine()` and `FoodRules()`) are intentionally unchanged in this stage to avoid silently replacing the current application's knowledge coverage with an empty set: the supplied project has no independently approved candidates/releases yet. New production wiring must explicitly use `from_active_release(...)` and handle the no-active-release condition. Until a qualified review team has created and promoted a real release, the project remains a development/demo system and must not be represented as clinically validated. The default-constructor cutover and application/API wiring are a separately gated follow-up, not an implicit fallback in the approved loader.

### Verification

Run on Windows:

```powershell
python -m pytest tests\test_knowledge_release.py tests\test_knowledge_curation.py tests\test_evidence_review.py tests\test_evidence_ingestion.py tests\test_rule_engine.py tests\test_food_rules.py -q
```

The implementation environment reported **124 passed** for this focused governance/runtime-loader suite. Full-suite collection in that environment remains blocked by missing optional project dependencies (`Flask` and `scikit-fuzzy`); this is not a full-suite pass.

### Explicitly not included

- No existing legacy rule was auto-approved or promoted.
- No actual clinical release was created or activated.
- No CLI/API endpoints for release management, signed external attestations, multi-party signatures, or application-wide default-loader cutover were added in this stage.

## Stage 3 — Release-management CLI and application runtime integration

**Status:** implementation complete in this snapshot; Windows verification pending.

### Added

- `scripts/manage_knowledge.py` provides `candidates`, `releases`, `inspect`, `create`, `promote`, `rollback`, and `status` commands. Release creation remains separate from promotion.
- `services.knowledge_release.inspect_release()` and `list_releases()` expose integrity-checked release inspection and inventory.
- `ReasoningService.from_active_release()` constructs interaction and food-rule services from the same active release and rejects a release mismatch.
- `RXLOGIC_KNOWLEDGE_MODE=active_release` switches the API's reasoning entry point to the fail-closed active-release loaders. `RXLOGIC_KNOWLEDGE_ROOT` optionally selects the knowledge directory. Unknown modes are rejected.
- `GET /api/knowledge/status` reports the configured mode and active release status. It never mutates governance state.
- `tests/test_knowledge_management_cli.py`, `tests/test_knowledge_runtime.py`, and API status tests cover the new boundaries.

### Security and deployment boundary

- Release-management mutations are deliberately CLI-only in this stage. The current application has anonymous session cookies but no authenticated staff identity/authorization system. Exposing promote/rollback HTTP endpoints with caller-supplied role strings would be unsafe; no such endpoints were added.
- CLI actor IDs and roles are audit assertions, not authentication. Restrict shell access to qualified, authorized staff and protect the host, filesystem, backups, and audit logs. A future authenticated identity provider and signed/dual-control approvals are needed before remote governance administration.
- `legacy_development` remains the backwards-compatible default and is explicitly unreviewed. Set `RXLOGIC_KNOWLEDGE_MODE=active_release` only after a real release has been independently approved and promoted. In that mode, missing/corrupt active release data causes a service error; there is no fallback.
- `/api/knowledge/status` reports `clinical_use_permitted: false` even for a promoted governance release. This project is not clinically validated or authorized for patient-care use.

### CLI examples (run from project root)

```powershell
python -m scripts.manage_knowledge candidates
python -m scripts.manage_knowledge releases
python -m scripts.manage_knowledge status
python -m scripts.manage_knowledge inspect RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX
python -m scripts.manage_knowledge create CANDIDATE-ID-1 CANDIDATE-ID-2 --actor-id curator-01 --rationale "Release rationale"
python -m scripts.manage_knowledge promote RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX --actor-id steward-01 --actor-role knowledge_steward
python -m scripts.manage_knowledge rollback RXK-YYYYMMDDTHHMMSSZ-XXXXXXXX --actor-id steward-01 --actor-role knowledge_steward
```

Global path overrides (`--knowledge-root`, `--curation-root`, `--staging-root`) must appear before the subcommand.

### Runtime configuration

```dotenv
RXLOGIC_KNOWLEDGE_MODE=active_release
# Optional; otherwise the repository knowledge/ directory is used.
RXLOGIC_KNOWLEDGE_ROOT=/absolute/path/to/knowledge
```

Check `GET /api/knowledge/status` after deployment. A 503 in active-release mode means no valid promoted release is available; do not switch to legacy mode merely to suppress that error in a clinical setting.

### Verification

The implementation environment can run the CLI, release, curation, evidence, and rule-loader suites, but does not have Flask installed, so the API test module could not be collected here. This snapshot must be verified in the project's Windows environment with its full `requirements.txt` installed. No full-suite pass is claimed.


### Stage 3 verification correction

Windows verification exposed an ordering defect in the module-level planning
wrapper: it validated an empty medication list before selecting the configured
knowledge runtime. The wrapper now resolves `RXLOGIC_KNOWLEDGE_MODE` first,
honors `RXLOGIC_KNOWLEDGE_ROOT`, and constructs the active-release-only service
when configured. Unknown modes are rejected before request validation.
Regression coverage asserts this precedence.

The structured and natural-language planning endpoints now return an explicit
HTTP 503 response for a missing/invalid active knowledge runtime rather than
producing a plan or exposing an unhandled configuration exception.

## Stage 4 — Release-integrity and audit-chain hardening

**Status:** implementation complete in this snapshot; Windows verification pending.

### Added

- Promotion/rollback audit records now form a SHA-256 hash chain. Each event commits to the prior event digest, and the runtime loader verifies the complete chain before loading active knowledge.
- Activation and rollback use a two-phase audit sequence: an intent event is durably appended, the active pointer is atomically replaced and bound to that intent digest, and a completion event is appended. A crash between pointer replacement and completion causes runtime loading to fail closed rather than treating an incomplete operation as committed.
- Rollback eligibility is based only on operations with verified completion events, not merely an intent record.
- The active pointer must reference a verified intent event whose matching completion event names the same release and manifest digest.
- Release manifests must declare exactly the three expected datasets, each with a well-formed SHA-256 digest. Publication policy must explicitly prohibit unreviewed runtime records and clinical-use claims.
- Added regression tests for audit-log tampering, forged pointers, missing dataset declarations, incomplete activation, and event-chain continuity.

### Security limitations and deployment requirements

- The hash chain is **tamper-evident**, not a digital signature. A privileged attacker who can rewrite the complete audit log and all local release files can recompute hashes. Production deployments still need externally anchored or digitally signed audit records, protected backups, filesystem access controls, and monitored administrative access.
- CLI actor IDs and role flags remain audit assertions, not authentication. This stage does not create an identity provider, HSM-backed signing, or dual-control authorization. Do not expose governance commands to untrusted users or remote callers.
- Concurrent promotion/rollback commands must be serialized by deployment operations. The local JSON/JSONL storage is not a distributed transaction manager or multi-host coordination system.
- If an older pre-Stage-4 promotion log exists without hash-chain fields, the new runtime deliberately rejects it. Do not edit or delete it to bypass validation. Preserve a backup and perform an explicitly reviewed migration before enabling active-release mode.
- No medication rule was auto-approved or promoted. A governance release is not clinical validation, regulatory clearance, or authorization for patient-care use.

### Verification

Focused local verification:

```powershell
python -m pytest tests\test_knowledge_release.py tests\test_knowledge_curation.py tests\test_evidence_review.py tests\test_evidence_ingestion.py tests\test_knowledge_management_cli.py -q
```

The implementation environment reports **48 passed** for this focused set. Its full-suite run is blocked at collection by the unavailable `scikit-fuzzy` dependency; Windows verification with the project's installed requirements remains required.

## Stage 5 — Final acceptance audit and rollback recovery coverage

**Status:** implementation complete in this snapshot; Windows verification pending.

### Added / corrected

- Added `docs/TASK_06_STAGE_5_ACCEPTANCE_AUDIT.md`, consolidating the evidence-to-candidate-to-approval-to-release lifecycle, promotion/rollback behavior, runtime fail-closed guarantees, API/CLI authorization boundaries, security limitations, and final acceptance disposition.
- Added a regression test that simulates interruption after rollback pointer replacement but before the rollback completion audit event. Runtime must reject the active pointer until a complete, verified operation exists.
- Corrected the README's test inventory from 14 to 22 test modules and replaced the superseded 262-test full-suite record with the user's Stage 4 Windows verification of 336 passed. The earlier 262-test result remains identified as historical.

### Verification

- Stage 5 focused release/curation/evidence/CLI/validation tests: **55 passed** in the implementation environment.
- A broader focused run including architecture-boundary tests reached 65 passed and one environment-blocked failure because `scikit-fuzzy` was not installed; the failing subprocess imports the normal reasoning service, not the release-governance path.
- Full-suite collection was blocked by missing `Flask` and `scikit-fuzzy` packages in the implementation environment. Package installation was unavailable due to network restrictions.
- The user's Stage 4 Windows full-suite result remains **336 passed**; it is not represented as a Stage 5 run.

Run the Stage 5 focused and full suites on Windows before marking this snapshot verified:

```powershell
python -m pytest tests\test_knowledge_release.py tests\test_knowledge_curation.py tests\test_evidence_review.py tests\test_evidence_ingestion.py tests\test_knowledge_management_cli.py tests\test_knowledge_validation.py tests\test_knowledge_runtime.py -q
python -m pytest -q
```

### Final boundary

Stage 5 does not add authenticated staff identity, multi-party authorization, digital signatures, distributed locking, clinical validation, or clinical-use authorization. The local audit chain remains tamper-evident rather than cryptographically signed. No existing rule is automatically promoted.
