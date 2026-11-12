# RxLogic

**An explainable neuro-symbolic AI demonstrator for medication-interaction reasoning and constraint-based schedule generation.**

[![Tests](https://github.com/raghavshikriwal/RxLogic/actions/workflows/tests.yml/badge.svg)](https://github.com/raghavshikriwal/RxLogic/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](runtime.txt)
[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen.svg)](https://rxlogic-ataf.onrender.com)

**[Open the live demonstration](https://rxlogic-ataf.onrender.com)**

> **Important deployment note:** The deployed Render instance does not host Ollama. Its structured medication-entry workflow is available; natural-language parsing requires a locally running Ollama service and is therefore not available on that hosted instance.

> **Educational demonstrator only — not a medical device.** RxLogic is a software engineering and AI coursework demonstration. It is not clinically validated, is not a substitute for a qualified healthcare professional, and must never be used to choose, change, time, start, stop, or combine real medication. All examples and test cases are synthetic demonstrations.

RxLogic separates optional neural language understanding from its deterministic symbolic reasoning core. A local LLM can convert a natural-language description into typed input. The actual interaction-rule evaluation, uncertainty refinement, constraint solving, planning, and explanation are performed by conventional, inspectable software. The structured-input workflow does not require an LLM.

---

## Contents

1. [Project overview](#1-project-overview)
2. [Key capabilities](#2-key-capabilities)
3. [Architecture and data flow](#3-architecture-and-data-flow)
4. [Frontend experience and user input](#4-frontend-experience-and-user-input)
5. [Technology stack](#5-technology-stack)
6. [Repository structure](#6-repository-structure)
7. [API overview](#7-api-overview)
8. [Local setup](#8-local-setup)
9. [Running the application](#9-running-the-application)
10. [Testing and verification evidence](#10-testing-and-verification-evidence)
11. [Deployment notes](#11-deployment-notes)
12. [Safety, scope, and known limitations](#12-safety-scope-and-known-limitations)
13. [Design decisions](#13-design-decisions)
14. [Future improvements](#14-future-improvements)
15. [License and project information](#15-license-and-project-information)

---

## 1. Project overview

RxLogic demonstrates how multiple classical AI techniques can cooperate in one explainable pipeline. It is designed around a deliberately safety-adjacent example domain so that the project can demonstrate rule-based knowledge representation, reasoning under uncertainty, constraint satisfaction, planning, and transparent output.

The project combines:

- **Knowledge representation and inference:** curated medication-pair rules evaluated by a forward-chaining rule engine.
- **Reasoning under uncertainty:** a Mamdani fuzzy-logic layer that refines confidence using evidence strength and source reliability.
- **Constraint satisfaction:** a dose-time scheduler using backtracking, a minimum-remaining-values (MRV) variable-ordering heuristic, and forward checking.
- **Goal-stack planning:** a planner that resolves scheduling goals and records its resolution trace.
- **Optional natural-language understanding:** a local Ollama model that extracts structured fields from text; it does not make the downstream decisions.
- **A web interface and API:** a React frontend communicates with a Flask backend and displays the pipeline's structured results.

A core architectural property is that the symbolic reasoning pipeline can run using structured input without calling the LLM. The LLM is an input convenience, not the authority for interaction decisions or schedule construction.

## 2. Key capabilities

### Reasoning and planning

- Normalize supported brand aliases and selected spelling variants to canonical names.
- Reject medication names that are not covered by the shipped knowledge base rather than silently treating them as safe.
- Evaluate curated interaction rules across medication pairs.
- Keep interaction severity, evidence strength, and derived confidence conceptually separate.
- Apply available food-related constraints and report conflicts with user-provided fields.
- Generate a feasible schedule subject to configured timing and separation constraints, or return a typed unsatisfiable result.
- Include rule identifiers, constraint identifiers, reasoning text, and a goal-resolution trace in the output.

### Application experience

- Structured medication-entry form with add/remove rows and field validation.
- Optional natural-language input mode when the backend can reach a local Ollama instance.
- Result presentation for the generated schedule, interaction warnings, coverage, name corrections, food guidance, and goal trace.
- Plan-history page backed by the API's plan-list endpoint.
- Responsive React layout built with Tailwind CSS.

### Backend and persistence

- Flask REST API with request validation and endpoint rate limits.
- Typed domain schemas and explicit domain exceptions.
- SQLAlchemy persistence with SQLite for local/test use and PostgreSQL configuration for deployment.
- Best-effort plan logging: a logging failure is designed not to turn an otherwise successful plan response into an API failure.
- Cached external drug-data lookups through the RxNav RxCUI and openFDA label-data integrations.

## 3. Architecture and data flow

The system is organized around a strict boundary between language parsing and symbolic reasoning.

```text
React + Vite frontend
        |
        | structured request or natural-language request
        v
Flask API (routes/api.py)
        |
        +---- structured input -------------------------------+
        |                                                      |
        +---- free text --> Ollama --> LLM parser --> schema --+
                                                               |
                                                               v
                                                Typed Medication objects
                                                               |
                                                               v
                                                Reasoning service
                                                               |
                 +----------------------+----------------------+-------------------+
                 |                      |                      |                   |
                 v                      v                      v                   v
          Name normalizer          Food rules             Rule engine        Coverage check
          aliases/variants         meal constraints       forward chaining  unknown-name guard
                 |                      |                      |
                 +----------------------+----------------------+
                                                               |
                                                               v
                                                   Fuzzy uncertainty layer
                                                               |
                                                               v
                                                   Goal-stack planner
                                                               |
                                                               v
                                                   CSP dose scheduler
                                                   backtracking + MRV
                                                   + forward checking
                                                               |
                                                               v
                                                   Explainable DailyPlan
                                                               |
                                      +------------------------+------------------+
                                      |                                           |
                                      v                                           v
                              API response / React UI                     Plan log storage
                                                                         SQLite / PostgreSQL
```

### Pipeline stages

1. The user submits either structured fields or a natural-language description.
2. For natural-language input only, the LLM parser requests structured output from Ollama and validates it against the application's schema.
3. The name normalizer resolves supported aliases and selected close variants; unresolved names are surfaced as unknown.
4. Coverage is evaluated against the project's curated knowledge base. An unknown medication does not receive an all-clear result.
5. Food-rule processing applies configured guidance where the input leaves the field unspecified and reports conflicts rather than silently hiding them.
6. The rule engine evaluates medication pairs against the curated interaction rules.
7. The uncertainty layer refines confidence using evidence and source-reliability inputs; severity is a separate concept.
8. The CSP scheduler attempts to satisfy dose-frequency, preferred-time, meal-window, and interaction-separation constraints. If no solution exists, it fails explicitly instead of silently weakening a constraint.
9. The planner records the order in which goals were resolved.
10. The API serializes the result and attempts to log the plan.
11. The frontend presents the schedule and supporting reasoning information returned by the backend.

## 4. Frontend experience and user input

The frontend is a React single-page application with two main destinations: **Plan** and **History**.

### 4.1 Plan page

The Plan page introduces the project and provides a medication form with two input modes.

**A. Add medications (structured mode)**

The user enters one medication per row. The available fields in the current form are:

| Field | What the field represents | Input behavior |
|---|---|---|
| Medication name | Name to be checked against the supported knowledge base | Required for each active row; text input |
| Dosage (mg) | Optional numeric dosage value | Optional; if supplied, must be a valid non-negative number |
| Times per day | Frequency value used by the scheduling demonstration | Required numeric value from 1 through 6 |
| Preferred timing | One of No preference, Morning, Afternoon, Evening, or Night | Select control; defaults to No preference |
| Food instruction | Not specified, With food, or Without food | Select control; defaults to Not specified |

The user can select **Add another medication** to add a row and **Remove** to remove an extra row. At least one active medication row is required. Empty unused rows are ignored. The form validates the medication name, dosage (when supplied), and frequency before submission.

**B. Describe in words (natural-language mode)**

The user can type a plain-language description into the text area. The current UI allows up to 4,000 characters. The parser is intended to extract medication names and any dosage, frequency, timing, or food details that the model can reliably identify. This mode requires a reachable local Ollama service and the configured model. It is not enabled on the hosted Render demo described below.

For a UI walkthrough or classroom demonstration, use only synthetic, instructor-provided sample data. Do not enter personal health information or real medication regimens. A natural-language parser can misunderstand text; its output must not be treated as medical advice.

**Illustrative text format (synthetic placeholder only):**

```text
DemoMed-A, one time per day, preferred in the morning.
DemoMed-B, two times per day, no preferred time was provided.
```

These placeholder names are for explaining the input format only. They are not entries in the shipped knowledge base and are not expected to generate a valid plan.

### 4.2 Plan result

When a request succeeds, the result components display the information returned by the API. Depending on the result, this includes:

- **Schedule timeline:** medication labels, scheduled times, and the associated reasoning/constraints.
- **Interaction warnings:** matched rule information, severity, evidence, confidence, and configured separation or ordering details.
- **Coverage summary:** how many distinct medication names were checked and which names remain unchecked.
- **Name corrections:** supported alias or fuzzy-name resolutions made before reasoning.
- **Food guidance:** applicable meal requirements and whether the input matched or conflicted with the configured rule.
- **Goal trace:** the order in which the planner resolved its goals.

An empty warning list must not be interpreted as proof that every possible interaction was checked. Always read the coverage information and the application's educational disclaimer.

### 4.3 History page

The History page requests recent saved plans from the backend. It displays the available plan records, input names, creation time, input source, warning count, and expandable schedule entries. A small warning-count trend is shown for the returned history records. The current API history response is limited to a maximum of 100 records; the frontend requests a recent subset.

### 4.4 Navigation and errors

The navigation provides access to the Plan and History views. Validation errors are shown near the relevant fields or form. Backend failures are presented through an error banner rather than being silently converted into a successful-looking result.

## 5. Technology stack

| Area | Technology | Responsibility |
|---|---|---|
| Frontend | React 18 | Component-based user interface |
| Frontend tooling | Vite 5 | Development server and production build |
| Styling | Tailwind CSS 3 | Responsive utility-first styling |
| Client routing | React Router 6 | Plan and History navigation |
| Backend | Flask 3 | REST API and application serving |
| Rate limiting | Flask-Limiter | Endpoint request limits |
| Language parsing | Ollama + `phi3:mini` (local) | Optional free-text extraction |
| Core reasoning | Python | Rules, normalization, planning, and CSP scheduling |
| Fuzzy inference | scikit-fuzzy | Mamdani-style confidence refinement |
| External drug data | RxNav and openFDA | RxCUI resolution and label-data lookup |
| Persistence | SQLAlchemy 2 | SQLite and PostgreSQL database access |
| Migrations | Alembic | Database schema migration tooling |
| Testing | pytest + pytest-cov | Automated tests and coverage reporting |
| Deployment | Render + Gunicorn | Hosted Flask service and built frontend |

## 6. Repository structure

```text
RxLogic-main/
├── app.py                         # Flask application entry point
├── extensions.py                  # Shared Flask extensions
├── routes/
│   └── api.py                     # API routes and request/response boundary
├── models/
│   ├── schemas.py                 # Typed domain schemas
│   ├── exceptions.py              # Typed domain exceptions
│   └── database.py                # SQLAlchemy database configuration/models
├── services/
│   ├── llm_parser.py              # Optional Ollama natural-language parser
│   ├── name_normalizer.py         # Alias and spelling normalization
│   ├── food_rules.py              # Meal-related rule processing
│   ├── rule_engine.py             # Forward-chaining interaction rules
│   ├── uncertainty.py             # Fuzzy confidence refinement
│   ├── csp_scheduler.py           # Constraint-satisfaction scheduler
│   ├── planner.py                 # Goal-stack planner
│   ├── reasoning_service.py       # Pipeline orchestration
│   ├── drug_data_client.py        # RxNav/openFDA client and cache
│   └── plan_log_service.py        # Plan persistence translation
├── knowledge/
│   ├── interaction_rules.json     # Curated interaction knowledge
│   ├── food_rules.json            # Curated meal-related rules
│   ├── drug_aliases.json          # Supported aliases and variants
│   └── cache/                     # Cached external lookup responses
├── frontend/
│   ├── src/
│   │   ├── components/            # Form, result, warning, trace and layout UI
│   │   ├── pages/                 # Home/Plan and History pages
│   │   ├── hooks/                 # Shared React hooks
│   │   ├── api.js                 # Frontend API client
│   │   ├── App.jsx                # Application routes/layout
│   │   └── index.css              # Global styles
│   ├── package.json               # Frontend scripts/dependencies
│   └── vite.config.js              # Vite development configuration
├── tests/                         # 14 pytest test modules
├── alembic/                       # Database migration environment/history
├── scripts/                       # Knowledge-base maintenance scripts
├── .github/workflows/             # CI test workflow
├── live_llm_smoke_test.py         # Manual live Ollama integration check
├── requirements.txt               # Python dependencies
├── runtime.txt                    # Python runtime pin
├── Procfile                       # Gunicorn process declaration
└── README.md
```

## 7. API overview

All application endpoints are under `/api`. The API validates request bodies and maps known domain failures to explicit HTTP responses.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/info` | GET | Application metadata |
| `/api/plan` | POST | Create a plan from structured medication data |
| `/api/plan/nl` | POST | Parse natural-language input, then use the same reasoning pipeline |
| `/api/plans` | GET | List recent plans for the caller's session; supports a `limit` query parameter |

### 7.1 Structured request shape

The structured endpoint expects a JSON object containing a `medications` array. Each medication object can include `name`, `dosage_mg`, `frequency_per_day`, `timing_preference`, and `with_food`. The backend schema is authoritative for accepted values and defaults.

A minimal illustrative request shape (not a medical recommendation):

```json
{
  "medications": [
    {
      "name": "<supported-demo-name>",
      "frequency_per_day": 1,
      "timing_preference": "no_preference"
    }
  ]
}
```

### 7.2 Response information

A successful plan response includes the schedule entries and, where applicable, warnings, goal trace, coverage summary, name resolutions, and food guidance. The frontend consumes these response fields to render the result sections described above.

### 7.3 Known error categories

| Error category | Typical status | Meaning |
|---|---:|---|
| `schema_validation_error` | 400 | Invalid request shape or parsed output that fails schema validation |
| `unknown_medication` | 422 | One or more names are not covered after normalization |
| `insufficient_data` | 422 | No usable medication entries were provided |
| `no_feasible_schedule` | 422 | The configured constraints cannot be satisfied |
| `external_api_error` | 502 | External drug-data service failure |
| `llm_api_error` | 502 | Local Ollama service/model request failed |

The exact response body and accepted field values are defined by the current backend schemas and route implementation; consult `models/schemas.py` and `routes/api.py` when integrating another client.

## 8. Local setup

### 8.1 Prerequisites

- Windows 10/11 with PowerShell, macOS, or Linux.
- Python 3.12 (the repository runtime pin is in `runtime.txt`).
- Node.js and npm for frontend development/building.
- Git (optional, for cloning/version control).
- Ollama and the configured model only if testing natural-language mode.

### 8.2 Get the source

Clone the repository:

```bash
git clone https://github.com/raghavshikriwal/RxLogic.git
cd RxLogic
```

Alternatively, open the extracted project directory in VS Code.

### 8.3 Configure environment

Copy the example environment file and edit only the settings needed for your local environment.

**PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```bash
cp .env.example .env
```

Do not commit `.env`, database credentials, API keys, or other secrets. Keep secrets in environment variables or the deployment platform's secret settings.

### 8.4 Install backend dependencies

**PowerShell:**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, use the Python executable directly instead of changing machine-wide execution policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**macOS/Linux:**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 8.5 Install frontend dependencies

```powershell
cd frontend
npm ci
cd ..
```

Use `npm ci` for a reproducible install from the committed lockfile. `npm install` is also available when intentionally updating dependencies.

## 9. Running the application

### 9.1 Run the backend

From the repository root, with the virtual environment active:

```powershell
python app.py
```

The Flask development server is configured to listen on the local backend port (normally `http://127.0.0.1:5000`). Use a separate terminal for the frontend development server.

### 9.2 Run the frontend in development mode

From the repository root:

```powershell
cd frontend
npm run dev
```

Open the local Vite URL printed in the terminal (normally `http://localhost:5173`). The Vite configuration proxies `/api` requests to the local Flask backend. Keep both processes running while using the development UI.

### 9.3 Build the frontend

From the repository root:

```powershell
cd frontend
npm run build
cd ..
```

The production assets are generated in `frontend/dist/`. This repository tracks the built frontend bundle for its single-service Render deployment. After changing frontend source files, rebuild the bundle and include the updated `frontend/dist/` in the deployment commit; otherwise the hosted Flask app may serve an older bundle.

### 9.4 Optional local natural-language mode

Natural-language parsing requires Ollama to be installed and running locally, with the configured model available. For this repository's documented default:

```powershell
ollama pull phi3:mini
ollama serve
```

Ollama may already be running as a background service after installation. Confirm that the configured model is present with `ollama list`. The backend reads `OLLAMA_BASE_URL` and `OLLAMA_MODEL` from its environment; see `.env.example` and `services/llm_parser.py`.

If Ollama is unavailable, natural-language requests should return the explicit `llm_api_error` category. Structured input and the symbolic reasoning pipeline are designed to remain independent of Ollama.

### 9.5 Environment variables

| Variable | Documented default / behavior | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite in-memory default in application configuration | Database connection; configure PostgreSQL for a persistent deployment |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `OLLAMA_MODEL` | `phi3:mini` | Ollama model name |
| `FLASK_DEBUG` | `false` | Flask debug behavior; keep disabled in production |
| `LOG_LEVEL` | `INFO` | Application logging level |
| `PORT` | `5000` locally; hosting platform may set it | HTTP server port |
| `PYTHON_VERSION` | Platform-specific | Render runtime selection |

Check `.env.example`, `app.py`, and `services/llm_parser.py` for the authoritative configuration behavior before changing deployment values.

## 10. Testing and verification evidence

RxLogic has an automated pytest suite across **14 test modules**. The results below distinguish the full-suite run, focused test runs, and manually executed live-model verification. Counts from focused runs overlap with the full suite and must not be added together as separate unique tests.

### 10.1 Full automated suite — latest user-provided run

| Measure | Result |
|---|---:|
| Command | `python -m pytest -v` |
| Collected / passed | **262 / 262** |
| Failed | **0** |
| Duration | **90.62 seconds** |
| Platform reported by pytest | Windows (`win32`), Python 3.12.10, pytest 8.3.3 |

This result was captured from a local PowerShell run on November 12, 2026. It is evidence for that source state and environment; rerun the suite after subsequent code changes.

### 10.2 Focused verification runs discussed during project review

| Area | Command / method | User-provided result |
|---|---|---:|
| CSP scheduler | `python -m pytest tests/test_csp_scheduler.py -v` (previously reported run) | **27 passed** |
| Rule engine + reasoning service | `python -m pytest tests/test_rule_engine.py tests/test_reasoning_service.py -v` | **95 passed** |
| LLM parser unit tests | `python -m pytest tests/test_llm_parser.py -v` | **13 passed** |
| API routes | `python -m pytest tests/test_api.py -v` | **32 passed** |
| Database URL behavior | `python -m pytest tests/test_database.py -v` | **2 passed** |
| End-to-end pipeline | `python -m pytest tests/test_e2e.py -v` | **3 passed** |
| Full automated suite | `python -m pytest -v` | **262 passed** |

The focused API, database, and end-to-end runs total 37 passed test cases in those selected modules. The 95 interaction tests and other focused runs are also included in the full-suite result; they are not additional unique tests beyond the 262.

### 10.3 Coverage measurements reported during review

| Module | Reported coverage | Measurement scope |
|---|---:|---|
| `services/csp_scheduler.py` | **99%** | Focused scheduler coverage run; 176 statements, 1 missed (previously reported) |
| `services/llm_parser.py` | **100%** | `python -m pytest tests/test_llm_parser.py --cov=services.llm_parser --cov-report=term-missing -v`; 47 statements, 0 missed |

These are **module-specific coverage results**, not overall repository coverage. A single current full-project coverage percentage has not been established in the verification evidence recorded here.

To generate a fresh overall report locally:

```powershell
python -m pytest --cov=services --cov=models --cov=routes --cov-report=term-missing
```

### 10.4 Live Ollama smoke test

The project includes `live_llm_smoke_test.py`, which calls `services.llm_parser.parse_medications()` against a running Ollama model rather than mocking the model request.

The user-provided local verification recorded:

- Ollama version: `0.40.14`.
- Model available: `phi3:mini`.
- Direct model invocation returned the requested JSON-shaped output.
- `python live_llm_smoke_test.py` completed **3/3 cases** successfully.
- The three cases exercised extraction of medication names and frequency, plus timing and dosage fields where present.

This verifies a local parser-to-Ollama smoke-test path for those sample inputs. It does not prove general language-understanding accuracy, medical correctness, or hosted Ollama availability.

Run it locally after starting Ollama:

```powershell
python live_llm_smoke_test.py
```

### 10.5 What the tests cover

The 14 test modules exercise the following areas:

| Test module | Primary focus |
|---|---|
| `test_api.py` | Health/root routes, request validation, structured and text plan endpoints, error mapping, session-scoped history, and response fields |
| `test_architecture_boundaries.py` | Separation between parser, reasoning core, and external/network dependencies |
| `test_csp_scheduler.py` | Dose spacing, timing preferences, meal windows, interaction constraints, ordering, backtracking, and unsatisfiable cases |
| `test_database.py` | Database URL normalization |
| `test_drug_data_client.py` | RxCUI/label lookup behavior, caching, and external-service failure handling |
| `test_e2e.py` | Full reasoning pipeline scenarios and fail-safe handling of unknown names |
| `test_food_rules.py` | Food-rule validation, application, conflicts, and missing-rule behavior |
| `test_llm_parser.py` | JSON parsing, defaults, schema validation, and Ollama error handling |
| `test_name_normalizer.py` | Exact names, aliases, fuzzy matching safeguards, and normalization |
| `test_planner.py` | Goal ordering, trace generation, and warning propagation |
| `test_reasoning_service.py` | Orchestration, interaction flow, coverage, duplicate handling, and food guidance |
| `test_rule_engine.py` | Rule loading, pair matching, evidence, severity, coverage, separation, and ordering |
| `test_schemas.py` | Domain schema validation and defaults |
| `test_uncertainty.py` | Confidence refinement, evidence/source reliability, and bounds |

### 10.6 Reproduce the checks

Run the complete suite:

```powershell
python -m pytest -v
```

Run the API, persistence configuration, and end-to-end modules individually:

```powershell
python -m pytest tests/test_api.py -v
python -m pytest tests/test_database.py -v
python -m pytest tests/test_e2e.py -v
```

Run interaction and LLM parser tests:

```powershell
python -m pytest tests/test_rule_engine.py tests/test_reasoning_service.py -v
python -m pytest tests/test_llm_parser.py -v
```

Run focused coverage reports:

```powershell
python -m pytest tests/test_csp_scheduler.py --cov=services.csp_scheduler --cov-report=term-missing -v
python -m pytest tests/test_llm_parser.py --cov=services.llm_parser --cov-report=term-missing -v
```

The pytest-asyncio deprecation warning about an unset default fixture-loop scope appeared in some earlier runs. It was non-blocking and did not cause test failures. It should be addressed as a separate test-configuration cleanup if the installed plugin version continues to emit it.

### 10.7 Verification boundaries

Passing automated tests establish that the tested code paths behaved as expected in the reported local environment. They do **not** establish clinical validity, exhaustive knowledge-base coverage, production load capacity, penetration-test results, full accessibility conformance, or continuous uptime of the hosted service. Frontend browser QA and a fresh deployed-environment audit remain separate verification activities.

## 11. Deployment notes

The repository is configured for a single-service deployment in which Gunicorn runs the Flask application and Flask serves the committed frontend build output.

The project README's existing deployment configuration describes Render hosting and PostgreSQL through Neon. Deployment settings, environment variables, database connectivity, and hosted service health should be checked in the relevant provider dashboards before each evaluation or release. Do not publish secret values in source control or screenshots.

The hosted demonstration does not run Ollama. Therefore, use structured input for the hosted demonstration; use a local environment with Ollama for the natural-language parser demonstration.

## 12. Safety, scope, and known limitations

This project is intentionally an educational software demonstrator. It is **not a medical device, clinical decision-support system, prescribing tool, or source of medical advice**. It must not be used for real medication decisions.

Known limitations include:

- The interaction knowledge base is curated and incomplete. It does not cover every medication or every possible interaction.
- The shipped rule values and meal guidance have not been clinically validated by a qualified clinician for this project.
- The reasoning model does not account for all patient-specific factors, formulations, diagnoses, laboratory results, allergies, pregnancy status, organ function, or other context needed for real clinical decisions.
- Brand/alias and fuzzy name normalization is limited to the project's curated data and matching safeguards.
- A name outside the knowledge base is rejected rather than treated as safe. A complete coverage summary is important when interpreting any result.
- External RxNav/openFDA data access may fail, change, or be unavailable; local cache contents may be stale.
- Ollama is optional and local. Model output may omit or misinterpret information and is subject to schema validation, not clinical validation.
- Plan history is not a complete immutable clinical record. The current persistence implementation stores only the fields explicitly mapped by the plan-log service.
- The test suite uses software fixtures and synthetic scenarios; passing tests do not validate clinical recommendations.

Do not enter personal health information into a classroom demo. Use synthetic examples only. Any real medication question must be handled by a qualified pharmacist or physician.

## 13. Design decisions

- **Keep the reasoning core independent:** the parser and network-facing integrations are outside the symbolic reasoning core.
- **Use typed boundaries:** domain schemas and explicit exceptions make data contracts and failure modes inspectable.
- **Fail safely:** unknown names, invalid inputs, and unsatisfiable constraints produce explicit failures rather than reassuring but unsupported results.
- **Make outputs traceable:** rule IDs, constraint IDs, coverage, and planner traces expose why the system produced its output.
- **Keep the LLM optional:** structured input can exercise the reasoning pipeline without a running model.
- **Keep scope honest:** curated educational rules are not presented as comprehensive clinical knowledge.

## 14. Future improvements

- Independent clinical review and governance for any expanded knowledge base (without presenting the educational application as a clinical product).
- Broader automated tests for real database connectivity, migrations, persistence across restarts, and failure recovery.
- Dedicated frontend component, accessibility, and browser-based end-to-end tests.
- Deployment smoke tests for hosted API health, frontend/API integration, and database connectivity.
- A reproducible full-project coverage baseline and CI coverage reporting.
- More explicit data provenance/versioning for curated knowledge files and cached external data.
- Better observability, structured logs, and deployment diagnostics.
- Additional documentation and a reproducible evaluation/demo script using synthetic inputs only.

## 15. License and project information

Released under the [MIT License](LICENSE). See the license file for the complete terms.

- **Project:** RxLogic
- **Repository:** [github.com/raghavshikriwal/RxLogic](https://github.com/raghavshikriwal/RxLogic)
- **Live demonstration:** [rxlogic-ataf.onrender.com](https://rxlogic-ataf.onrender.com)
- **Academic context:** Artificial Intelligence coursework demonstration

---

*Documentation status: updated to record the project structure and verification evidence discussed on November 12, 2026. Re-run the commands and refresh the results after any relevant source-code, dependency, or environment change.*
