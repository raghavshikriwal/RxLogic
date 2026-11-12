# RxLogic — Task 01 Repository Audit

**Audit type:** Static repository and architecture review  
**Repository snapshot:** `RxLogic-main (25).zip` supplied in this conversation  
**Audit date:** 2026-11-13  
**Scope:** Existing source tree, medical knowledge assets, API/domain schemas, reasoning services, test inventory, and available local validation.

> **Safety boundary:** RxLogic currently describes itself as an educational demonstrator, not a medical device. This audit is an engineering assessment, not a clinical review of the correctness or completeness of individual medication rules. Nothing in this report validates a regimen or provides medical advice.

## 1. Executive summary

RxLogic has a useful separation between natural-language extraction and deterministic reasoning. Its current knowledge layer, however, is a small demonstration dataset rather than a comprehensive medical knowledge base. The next engineering step should be to establish a versioned, source-attributed knowledge model and ingestion/validation workflow before expanding the number of drugs or clinical facts.

### Repository inventory

| Area | Observed contents |
|---|---|
| Backend | Flask application and REST API |
| Frontend | React 18, Vite, React Router, Tailwind CSS |
| Domain model | Python dataclasses and enums in `models/schemas.py` |
| Reasoning | Rule engine, fuzzy confidence layer, planner, CSP scheduler |
| Persistence | SQLAlchemy with SQLite default and PostgreSQL URL support |
| External data client | RxNav RxCUI lookup and openFDA label lookup |
| Knowledge assets | JSON aliases, interaction rules, food rules, and RxCUI cache files |
| Tests | 14 test modules; 219 functions named `test_*` were counted statically |
| CI | GitHub Actions workflow runs pytest on Python 3.12 |

### Current knowledge-data counts

| Asset | Count | Interpretation |
|---|---:|---|
| Canonical medications in the interaction knowledge map | 10 | Small seed set |
| Medication-pair interaction rules | 12 | Curated examples, not an exhaustive interaction matrix |
| Brand/spelling aliases | 35 | Name-resolution aids, not 35 additional medicines |
| Food rules | 4 | Narrow meal-guidance coverage |
| RxCUI cache files | 10 | Cached concept lookups for the seed medications |

The 10 seed medications create 45 mathematically possible unique unordered pairs. The 12 stored rules cover only selected pairs. This arithmetic must **not** be interpreted as saying the other 33 pairs are clinically safe or even that all should have a warning. It means the current ruleset does not explicitly encode them.

The 12 rules currently have the following stored labels:

- Severity: 2 severe, 6 moderate, 4 mild.
- Evidence field: 5 strong, 5 moderate, 2 limited.
- Source label: 8 `openFDA label / clinical literature`, 4 `clinical literature`.

These are metadata values in the repository. The audit did not independently verify the clinical validity of each rule or its classification.

## 2. What is already good

1. **LLM boundary:** The natural-language parser is intended to extract typed medication fields; the architecture tests explicitly guard against the parser supplying downstream clinical decisions.
2. **Deterministic core:** Rule evaluation and scheduling are separate from the optional LLM path.
3. **Unknown-name handling:** The reasoning service checks knowledge coverage and rejects unsupported medication names instead of treating missing data as a clean interaction result.
4. **Explainability hooks:** Interaction records include rule identifiers, severity, evidence labels and source strings; plans include a goal trace and coverage summary.
5. **Separation of concerns:** API, schemas, reasoning services, persistence and frontend components are separated into distinct modules.
6. **Test intent:** The repository has tests for API behavior, architecture boundaries, scheduling, database behavior, food rules, normalization, planning, reasoning and uncertainty.
7. **Safety disclaimer:** README clearly labels the application as an educational demonstrator and warns against real-world medication use.

These are useful foundations and should be preserved during expansion.

## 3. Findings and gaps

### P0 — Resolve before expanding clinical content

#### F-01. No first-class, provenance-rich clinical knowledge model

**Evidence:** Clinical facts are currently represented in `knowledge/interaction_rules.json` and `knowledge/food_rules.json`. Their `source` values are free-text labels. Rule IDs are generated from list position (`RULE_000`, etc.).

**Risk:** A source label is not enough to reproduce or audit a clinical claim. There is no consistent source document identifier, exact label section/page, publication or revision date, jurisdiction, population, evidence excerpt, reviewer status, or dataset release identifier. List-position IDs can also change if rules are reordered.

**Required direction:** Introduce stable record IDs and source/evidence records. Every clinical assertion should carry provenance and review state. Preserve source documents or exact source locators where licensing permits.

#### F-02. Knowledge coverage is a small seed dataset

**Evidence:** 10 canonical medications, 12 interaction rules, 4 food rules and 35 aliases.

**Risk:** A larger-looking UI or an empty warning list can be mistaken for comprehensive checking. The current coverage model is medication-name coverage; it does not demonstrate that all clinically relevant interaction types for a covered medication have been evaluated.

**Required direction:** Report coverage by knowledge domain and record status, not only by recognized medication name. Distinguish `known`, `not evaluated`, `no evidence found`, `conflicting evidence`, and `reviewed no interaction identified`. Never translate missing data into a negative clinical claim.

#### F-03. Patient context is absent from the domain model

**Evidence:** `Medication` includes name, RxCUI, dosage in mg, frequency, timing preference and a food flag. There is no typed patient context for age, weight, allergy, pregnancy/lactation, diagnoses, renal function, hepatic function, or relevant laboratory results.

**Risk:** Many clinical safety facts are conditional on patient characteristics. The current engine cannot safely claim patient-specific suitability.

**Required direction:** Add a separate, optional and privacy-conscious patient-context model in a later task. Do not infer missing patient attributes. Until clinically validated, patient context must be used only for clearly bounded educational warnings, not treatment decisions.

#### F-04. Dosage input is not a validated dose checker

**Evidence:** The API parses `dosage_mg` into the `Medication` dataclass, but the current knowledge assets do not define product/formulation-specific approved dose ranges or patient-adjusted dosing rules.

**Risk:** Accepting a numeric dosage can create a false impression that dose appropriateness is checked.

**Required direction:** Rename or clearly label the current field as user-provided input, validate its type and bounds, and do not describe it as dose verification. A true dose knowledge module requires indication, age group, route, formulation, units, renal/hepatic adjustment, maximum dose, source and jurisdiction, plus clinical review.

### P1 — Required for a reliable knowledge platform

#### F-05. External API client is not a knowledge-ingestion pipeline

**Evidence:** `services/drug_data_client.py` can resolve RxCUIs and fetch one openFDA label result. `services/reasoning_service.py` wires the local JSON rule engine and food rules; it does not build its clinical rule set from these live lookups.

**Risk:** The existence of an API client may be mistaken for a current, comprehensive clinical database. RxCUI resolution and label retrieval do not themselves provide a validated interaction assessment.

**Required direction:** Build separate source adapters, raw-data staging, normalization, schema validation, deduplication, provenance retention, review, release/versioning and rollback. Keep network ingestion out of the request-time clinical reasoning path.

#### F-06. Drug identity needs richer concepts than a name/RxCUI map

**Evidence:** The current map is generic-name to RxCUI, with aliases stored separately.

**Risk:** A drug name alone does not always distinguish ingredient, salt, strength, dose form, route, release mechanism, combination product or brand-specific formulation.

**Required direction:** Model ingredient/substance, clinical drug, branded drug/product and package/formulation concepts separately. Preserve terminology identifiers and mapping relationships. Do not assume one RxCUI per generic string is sufficient for all use cases.

#### F-07. Evidence strength and fuzzy confidence need stronger semantics

**Evidence:** `services/uncertainty.py` maps a small set of evidence labels and source strings to hard-coded numeric scores and applies fuzzy inference.

**Risk:** A computed confidence value may be read as a clinically calibrated probability even though the inputs are manually assigned heuristics. Source-string matching is brittle, and unknown sources fall back to a default reliability score.

**Required direction:** Treat evidence grading, source quality, clinical severity and model confidence as distinct fields. Document the fuzzy score as an engineering heuristic unless calibrated against an independently reviewed dataset. Never use it to downgrade a serious warning or to infer safety.

#### F-08. Rule validation is not a formal release gate

**Evidence:** The rule engine validates some spacing/order fields at load time, but the repository does not expose a complete knowledge-schema validator or a review/release manifest for all clinical records.

**Risk:** Invalid enums, missing citations, duplicate pairs, stale facts or contradictory records can enter the live JSON dataset without a formal review gate.

**Required direction:** Add strict schemas, semantic validation, stable IDs, duplicate detection, referential-integrity checks, source freshness checks and an approval workflow before a knowledge release can be activated.

#### F-09. API input validation needs a dedicated hardening pass

**Evidence:** `routes/api.py` converts `frequency_per_day` with `int(...)` and passes `dosage_mg` and `with_food` from the request into the dataclass. The route-level parser does not itself establish all domain invariants or patient safety.

**Risk:** Type coercion can accept surprising values, and API validation is not a substitute for clinically valid dose checking.

**Required direction:** In a separate task, enforce strict types (including rejecting booleans where numeric values are expected), finite numeric values, explicit ranges, request-size limits and consistent validation errors. Keep business/clinical validation in a domain service with tests.

### P2 — Maintainability and delivery improvements

#### F-10. Frontend has no declared test or lint scripts

**Evidence:** `frontend/package.json` declares `dev`, `build` and `preview`; no test or lint script is present.

**Required direction:** Add frontend linting and component/API tests in a separate task. Add a CI frontend build job so backend tests do not provide the only automated quality signal.

#### F-11. CI covers Python tests only

**Evidence:** `.github/workflows/tests.yml` installs Python dependencies and runs pytest on Python 3.12; it does not build the frontend or validate knowledge JSON against a formal schema.

**Required direction:** Add deterministic CI jobs for Python tests, knowledge validation, frontend build, dependency/security checks and artifact checks.

#### F-12. Cache implementation needs operational hardening

**Evidence:** The client uses file-based JSON cache writes and creates the cache directory at import time. Cache entries have no explicit expiry/version metadata in the inspected implementation.

**Risk:** Concurrent writes, corrupt cache files, stale external data and import-time filesystem side effects can complicate reproducibility and deployment.

**Required direction:** Use atomic writes, explicit cache metadata/TTL, corruption handling, configurable cache path and observability. Keep raw source payloads separate from normalized clinical assertions.

## 4. Validation performed for this audit

| Check | Result | Notes |
|---|---|---|
| ZIP inventory | PASS | 113 archive entries inspected |
| Python compileall | PASS | `app.py`, `extensions.py`, `models`, `routes`, `services`, `scripts`, and `tests` compiled |
| Knowledge JSON parsing/counts | PASS | Three primary knowledge JSON files parsed and counted |
| pytest collection/run | BLOCKED | 4 collection errors: missing `flask` for API tests and missing `skfuzzy` for reasoning/uncertainty tests |
| Frontend build | NOT RUN | Dependencies were not installed in the audit environment; package scripts contain a build command |
| Clinical correctness review | NOT PERFORMED | Requires qualified clinical review against current authoritative references |
| Security/dependency audit | NOT PERFORMED | Requires dedicated tooling and environment |

The pytest command was `python -m pytest -q`. It stopped during collection with:

- `ModuleNotFoundError: No module named 'flask'`
- `ModuleNotFoundError: No module named 'skfuzzy'`

No test pass rate is claimed. The local interpreter was Python 3.13, while the checked-in CI workflow targets Python 3.12; compatibility should be verified in the project's supported Python version.

## 5. Recommended target architecture

Use a staged, versioned knowledge platform rather than allowing runtime API calls or LLM output to directly become clinical facts.

```text
Authoritative sources
  ├── Drug labels / regulatory data
  ├── Standardized drug terminology
  ├── Clinical guidelines
  ├── Disease classifications / terminology
  └── Reviewed literature
          |
          v
Source adapters (one per provider; license-aware)
          |
          v
Immutable raw-source archive + retrieval metadata
          |
          v
Normalization and terminology mapping
          |
          v
Strict schema + semantic validation + deduplication
          |
          v
Evidence/provenance records + human review workflow
          |
          v
Versioned knowledge release (approved snapshot)
          |
          v
Read-only runtime query/reasoning layer
          |
          v
Explainable result + coverage state + source references
```

### Proposed knowledge domains

1. Drug substances and ingredients.
2. Clinical drug products, brands, strengths, dose forms and routes.
3. Drug-drug interactions.
4. Drug-food and drug-supplement interactions.
5. Contraindications and precautions.
6. Adverse effects and serious safety warnings.
7. Indication-specific dosing references (only after clinical governance is in place).
8. Disease and condition concepts.
9. Patient factors and risk modifiers.
10. Laboratory monitoring and relevant biomarkers.
11. Clinical guidelines and treatment pathways.
12. Medical terminology, synonyms and code mappings.
13. Source documents, evidence records, review status and release history.

### Minimum provenance fields for every clinical assertion

- Stable assertion ID and assertion type.
- Subject and object concepts, with terminology identifiers where applicable.
- Exact claim text and structured attributes.
- Publisher/source organization and source document identifier.
- Canonical source URL or licensed document locator.
- Section/table/page/label field supporting the claim.
- Publication, revision and retrieval dates when available.
- Jurisdiction and applicable population.
- Evidence grade and evidence rationale, separate from severity.
- Reviewer identity/role or review record, review date and status.
- Dataset release ID, source content hash and supersession/withdrawal state.

Do not invent or auto-fill missing provenance. Missing evidence should remain explicit.

## 6. Suggested implementation sequence

| Task | Scope | Exit criteria |
|---|---|---|
| 01 | Repository audit and target blueprint | This report reviewed; scope agreed |
| 02 | Knowledge schema and validation foundation | Versioned schemas, stable IDs, provenance model, validators and tests; existing seed data migrated without adding unverified clinical claims |
| 03 | Source ingestion framework | Source adapters, raw staging, licensing metadata, retries, atomic cache and reproducible imports |
| 04 | Drug identity catalog | Ingredient/product/brand/formulation concepts and terminology mappings |
| 05 | Interaction knowledge module | Provenance-backed interaction records, evidence state, review workflow and domain coverage |
| 06 | Contraindications and adverse effects | Separate structured domains with traceable sources |
| 07 | Food/supplement and monitoring knowledge | Structured requirements, monitoring concepts and applicability |
| 08 | Disease and clinical concepts | Terminology-backed condition catalog and source governance |
| 09 | Patient-context model | Consent/privacy design, typed optional context, missing-data handling and safety tests |
| 10 | Retrieval and explainability | Evidence retrieval, citations, knowledge-release version in every result |
| 11 | CI, security and quality gates | Backend, frontend, data validation and dependency checks |
| 12 | Clinical governance and validation plan | Qualified review process, intended-use definition and regulatory assessment |

### Task 02 should be the next implementation task

Task 02 should create the **knowledge schema and validation foundation**, not bulk-import more medication facts. It should:

- Define versioned schemas for drug concepts, clinical assertions, evidence sources and dataset releases.
- Give records stable identifiers independent of file order.
- Validate required provenance and domain-specific invariants.
- Add duplicate and reference-integrity checks.
- Migrate the existing 10-drug/12-rule/4-food-rule seed dataset while preserving its current meaning and clearly marking legacy evidence metadata as incomplete/unverified.
- Add tests proving that incomplete provenance cannot be promoted to an approved release.
- Keep runtime behavior backward-compatible until a separately tested migration is ready.

## 7. Explicit non-goals for this audit

- No clinical rule has been added, removed or reclassified.
- No new medication, dosage, contraindication or disease claim has been introduced.
- No patient data has been added.
- No API or UI behavior has been changed.
- No claim of clinical validation, regulatory compliance or production readiness is made.

**Audit conclusion:** Preserve the existing neuro-symbolic separation and unknown-medication guard. Build provenance, data modeling, validation and release governance first; expand clinical coverage only through authoritative, license-compliant sources and qualified review.
