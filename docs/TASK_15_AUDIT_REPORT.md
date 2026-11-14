# Task 15 — Audit, integration and validation report

**Scope:** the Task 15 overlay (clinical knowledge profile API, curation/release extensions, label-drafting aid,
evidence dashboard) was merged onto the Task 14 repository and audited. No clinical content was added, approved
or invented. This report states only what was actually run.

## 1. Verification limits of the audit environment (read first)

The audit sandbox had **no network access**. `pip install` and `npm install` both failed, and `pytest`, SQLAlchemy,
Flask-Limiter, scikit-fuzzy, Vite and react-router-dom were not installed. Consequently:

| Requested command | Status |
|---|---|
| `pytest` | **Not run.** Real pytest was unavailable. |
| `cd frontend && npm install` | **Not run** (no network). |
| `npm test` | **Not run as written.** Its two test files were run with `node --test` using React 19.2.8 / esbuild 0.28.2 found preinstalled on the machine (the project declares React ^18.3.1). |
| `npm run build` | **Not run.** Vite is not installed. A substitute esbuild compile of `src/main.jsx` (react-router-dom left external) succeeded; that checks JSX/import syntax only. It is **not** a production build and does not exercise Tailwind. |

To get some signal anyway, a small stand-in test runner (supports `raises`, `parametrize`, fixtures, `tmp_path`,
`monkeypatch`, `capsys`, `caplog`, `mock.patch`) and a no-op Flask-Limiter stub were written **outside** the repository
and are not shipped. Results from them are labelled "stand-in runner" below and **must not be read as a pytest pass**.

## 2. Results actually obtained

| Run | Result |
|---|---|
| Stand-in runner, Task 14 base (27 files that can be collected) | 352 passed, 1 failed |
| Stand-in runner, merged project (28 files that can be collected) | **482 passed, 1 failed** |
| Task 15 backend tests alone | 97 passed before the audit changes, **130 passed** after (33 added) |
| Frontend (`node --test`, see above) | 15 passed before the audit changes, **26 passed** after |
| Design-token guard mutation check | Re-introducing `rounded-xl` made the guard fail (1 failure), restoring it passed |

The single failing test, `test_architecture_boundaries.py::test_reasoning_pipeline_runs_with_llm_and_network_modules_blocked`,
fails identically on the Task 14 base: its subprocess imports `skfuzzy`, which is not installed here. It is an
environment failure, not a regression, but it has **not** been shown to pass.

**Nine test files could not be collected here** (missing SQLAlchemy or scikit-fuzzy) and were therefore **not run**:
`test_api`, `test_app_security`, `test_database`, `test_e2e`, `test_knowledge_runtime`, `test_llm_providers`,
`test_reasoning_service`, `test_task12_audit`, `test_uncertainty`. These cover the existing `/api/plan` contracts,
database compatibility and fuzzy reasoning. The merge touched `app.py` only to register one additional blueprint
(two added lines), so no existing route was edited, but the existing API contract and database compatibility are
**unverified by execution** until `pytest` is run on a normal install.

## 3. Repository comparison

Task 14 repository vs Task 15 overlay: 12 files added, 15 modified, 0 deleted. All existing reasoning modules
(`csp_scheduler`, `rule_engine`, `uncertainty`, `planner`, `llm_parser`, `name_normalizer`, `food_rules`,
`reasoning_service`), `routes/api.py`, `models/`, and the 24-medication catalog are untouched.
`services/clinical_reasoning.py` changed by one import: its private approval predicate now delegates to the shared
`is_release_usable` with identical logic (verified by diff).

## 4. Backend validation

| Requirement | Finding |
|---|---|
| Only approved findings from the active release are displayed | Confirmed. Findings require an integrity-verified active release **and** `is_release_usable`. Development mode shows none. |
| Unapproved findings never appear as approved | Confirmed for domains. **Defect fixed:** development records were returned with their stored `review_status` (even `clinically_approved`); they are now labelled `unverified_development_record` and the stored value is kept as `recorded_review_status`. |
| Interaction approval | **Defect fixed:** the interaction section treated the legacy development label `reviewed` as approval and ignored source requirements. Only `clinically_approved` with a source now counts. |
| Conflicting evidence identified | Confirmed for the 12 domains; **fixed** for interaction rules that carry an explicit `conflicting_evidence` state. |
| Missing evidence vs negative finding | Confirmed. Empty = `not_assessed` with an explicit missing-evidence message. Excluded records now carry an `exclusion_reason` (e.g. `conflict_assessment_missing`). |
| Citations and locators preserved | Confirmed for domains; interaction findings now keep `source_locator`; findings flag unresolved source references (`all_sources_resolved`). |
| API validation | Unknown names → 404, release unavailable → 503, invalid mode → 503. **Defect fixed:** the generic `ValueError` handler echoed internal error text (which can contain file paths); it now returns a fixed message and logs the detail. |
| Existing API contracts | Unchanged; the two endpoints are additive. |
| Alias matching | **Fixed:** a record filed under an alias is now matched to the canonical medication. |

## 5. The 24 medications

All 24 identities are present, unique, resolve by canonical name and alias, and every catalog name also exists in
the runtime medication map used by the release builder. Each profile returns all 12 domains plus
drug–drug interactions (13 sections). `test_every_medication_receives_only_its_own_findings` (24 cases) shows that
findings for one medication never appear under another and that the RxCUI returned matches the catalog.

RxCUI verification: the catalog RxCUIs for the **10** medications that have a local lookup cache match that cache.
The other **14** have no cache in the repository and could **not** be re-verified offline; run
`python -m scripts.verify_rxcuis` with network access.

## 6. Evidence governance

`test_full_pipeline_all_twelve_domains_reach_the_profile_only_through_an_active_release` drives
ingestion → evidence review → candidate → independent clinical approval → release → two release reviews →
promotion → runtime retrieval using synthetic fixtures. Existing tests confirm authors cannot approve their own
candidates, approval needs an explicit conflict assessment, approved candidates are hash-bound to their content, and
releases are immutable. The label-drafting aid only copies verbatim label text, never assigns evidence strength and
leaves structured sections incomplete so they fail validation until a human completes them. No code path approves
AI-generated content.

## 7. Frontend

Findings and fixes: `rounded-xl` is not defined in the project's replaced Tailwind border-radius scale, so the new
cards rendered with square corners (the same unstyled class exists in the older `MedicationForm.jsx`, left untouched).
Every section now shows: approved findings, evidence source, source locator (or "not recorded"), evidence
strength, review status (from the data), conflict status, missing-evidence status, awaiting-approval records
(ID, review state, conflict state, reason; no claim text), conflicting records, and an unresolved-source warning.
Cards add a section-status summary, a development-mode notice and expand/collapse-all; headers stack on narrow
screens. Nothing is hard-coded or filled in. **Not visually inspected in a browser** (none available here).

## 8. Remaining clinical evidence gaps

- `knowledge/clinical_assertions.json` contains **zero** assertions. For all 24 medications, all 12 domains are
  *not assessed*. No source has been ingested for approved use and no qualified reviewer has approved anything.
- 40 development interaction rules exist, all `needs_clinical_review`; none is shown as a finding.
- Interaction rules have no mandatory explicit conflict assessment at curation time (only the 12 clinical-assertion
  types do). This predates Task 15 and was left unchanged; it should be closed in a governance task.
- Dosage, contraindication, adverse-effect, mechanism, indication and interaction content must come from
  authoritative sources (e.g. FDA labels) via the workflow above and be approved by an independent qualified
  pharmacist or physician. Nothing here is clinically validated.
- `frontend/dist/` was **not rebuilt**. The committed bundle predates all Task 15 UI work; run `npm run build`
  before serving the production bundle.

## 9. Files

Added: `docs/TASK_15_CHANGELOG.md`, `docs/TASK_15_AUDIT_REPORT.md`, `routes/knowledge_api.py`,
`scripts/draft_candidates.py`, `services/clinical_profile.py`, `services/label_drafting.py`,
`tests/test_task15_clinical_knowledge.py`, `frontend/src/lib/clinicalProfile.js`,
`frontend/src/lib/clinicalProfile.test.js`, `frontend/tests/render.test.mjs`,
`frontend/src/components/{KnowledgeSection,MedicationKnowledge,MedicationProfileCard}.jsx`.

Modified: `.github/workflows/tests.yml`, `.gitignore`, `README.md`, `app.py`, `frontend/package.json`,
`frontend/src/api.js`, `frontend/src/components/{ClinicalAssessment,PlanResult}.jsx`,
`knowledge/clinical_assertions.json`, `reports/knowledge_coverage.json`, `services/clinical_knowledge.py`,
`services/clinical_reasoning.py`, `services/knowledge_coverage.py`, `services/knowledge_curation.py`,
`services/knowledge_release.py`.

Changed in this audit pass on top of the Task 15 delivery: `services/clinical_profile.py`,
`routes/knowledge_api.py`, `frontend/src/components/{KnowledgeSection,MedicationProfileCard,ClinicalAssessment}.jsx`,
`frontend/src/lib/clinicalProfile.js`, `frontend/src/lib/clinicalProfile.test.js`, `frontend/tests/render.test.mjs`,
`tests/test_task15_clinical_knowledge.py`, `.github/workflows/tests.yml`, `README.md`, `docs/TASK_15_CHANGELOG.md`.
