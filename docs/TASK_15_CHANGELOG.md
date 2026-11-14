# Task 15 — Clinical knowledge coverage pipeline, profile API and UI

## Purpose
Make RxLogic an explainable medication-reasoning demonstrator whose clinical
sections are filled **only** from evidence that has passed the existing
governance workflow. Nothing in this task writes clinical content.

## What this task does *not* do
- It adds **no** clinical assertions. `knowledge/clinical_assertions.json` still
  contains only empty arrays, so every section honestly reads
  "not assessed" until real, reviewed evidence is released.
- It does not fetch sources, approve anything, or promote releases.
- It does not generate or recommend patient-specific doses.

## Backend
| Area | Change |
|---|---|
| `services/clinical_knowledge.py` | Eight new optional monograph domains (overview, drug class, therapeutic category, mechanism of action, approved indications, precautions, adverse effects, drug–supplement interactions). Records in them require a `source_locator`. Shared `is_release_usable()` is the single "approved and usable" definition. Older datasets without the new keys stay valid. |
| `services/knowledge_curation.py` | Eight new candidate types; optional `source_locator` / `source_excerpt` on all clinical-assertion types; the conflict-assessment gate covers every clinical-assertion type. |
| `services/knowledge_release.py` | `create_release` builds all 12 domains from one mapping and applies the same duplicate guard. Release hashing, dual review, promotion and rollback are unchanged. |
| `services/clinical_profile.py` | Read-only per-medication profile: approved findings (verified active release only), awaiting-approval IDs, conflicts, missing evidence, resolved source references. Development files are never an approval authority and their claim text is withheld. |
| `routes/knowledge_api.py` | `GET /api/medications` and `GET /api/medications/<name>/clinical`. Existing endpoints are unchanged. Fail-closed 503 when the active release is unavailable; 404 for unknown names. |
| `services/label_drafting.py`, `scripts/draft_candidates.py` | Authoring aid: copies verbatim sections of an ingested openFDA label into draft rule files with section locators. Never assesses evidence strength, never approves. Structured sections (contraindications, dosage) are emitted incomplete so they fail validation until a human completes them. |
| `services/knowledge_coverage.py` | Coverage report v1.2.0 adds `monograph_domains`. |

## Frontend
`ClinicalAssessment.jsx` now also shows `MedicationKnowledge`, which loads each
scheduled medication's profile from the backend. Expandable `KnowledgeSection`
cards show approved findings, source citations with locators, evidence
strength, review status, conflict status, applicability, missing evidence and
conflicting evidence. Zero-count sections are shown as "Not assessed".

## How content gets in (the only path)
1. Ingest a source: `python -m scripts.fetch_medical_source …` or `scripts.ingest_evidence`.
2. A reviewer accepts it: `python -m scripts.review_evidence decide … accepted_for_curation`.
3. Optionally draft rule files: `python -m scripts.draft_candidates --evidence-id EVD-… --medication metformin --out-dir drafts`.
4. A human author completes/appraises a draft and runs `python -m scripts.manage_knowledge candidate-create --type … --rule-file … --evidence-id EVD-… --author-id …`.
5. An independent pharmacist/physician approves: `candidate-decide`.
6. A steward assembles a release, two release reviews are recorded, an independent promoter activates it.
7. Run the app with `RXLOGIC_KNOWLEDGE_MODE=active_release`.

## Tests
- Python: `tests/test_task15_clinical_knowledge.py` (all 24 identities, lookups, traceability, approved vs unapproved, conflicts, missing knowledge, interaction assessment, drafting, full release pipeline, HTTP API).
- Frontend: `cd frontend && npm test` (helper unit tests + server-side render tests; no new dependencies).

## Audit pass (integration and validation)

Changes made while auditing the Task 15 delivery against the Task 14 repository. See
`docs/TASK_15_AUDIT_REPORT.md` for evidence and remaining gaps.

- `services/clinical_profile.py`: interaction rules are approved only when explicitly `clinically_approved`
  (the legacy development label `reviewed` is no longer treated as approval) and cite at least one source;
  explicit `conflicting_evidence` rules are reported as conflicts; interaction findings keep `source_locator`;
  excluded records carry an `exclusion_reason`; development records are labelled `unverified_development_record`
  (the stored value moves to `recorded_review_status`); findings carry `all_sources_resolved`; records filed under
  an alias are matched to the canonical medication.
- `routes/knowledge_api.py`: configuration errors no longer echo internal error text (file paths) to clients.
- Frontend: `rounded-xl` is not in this project's Tailwind radius scale and rendered as no style, so the new cards
  lost their rounded corners; replaced with `rounded-lg`. Cards now show review status from the data, per-finding
  locator (or "not recorded"), unresolved-source warnings, itemised awaiting/conflicting records, a section status
  summary, a development-mode notice and expand/collapse-all. A test guards against utility classes outside the
  design-system scale.
- CI runs `npm run build` after the frontend tests.
