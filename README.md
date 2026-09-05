# RxLogic

**A neuro-symbolic AI agent for medication scheduling and drug-interaction reasoning.**

A small, locally-hosted LLM handles natural-language *understanding* at the edges of the system. Every actual decision — interaction detection, risk confidence, dose scheduling, conflict resolution — is made by classical, explainable AI: a forward-chaining rule engine, a fuzzy-logic uncertainty layer, a constraint-satisfaction scheduler, and a goal-stack planner. Disable the LLM entirely and the system still works, end to end, from a structured form.

> ⚠️ **Educational demonstrator, not a medical device.** RxLogic illustrates neuro-symbolic reasoning applied to a safety-adjacent domain. It is not a substitute for a pharmacist or physician and must not be used for real medication decisions. See [§8 Scope, Safety & Limitations](#8-scope-safety--limitations).

---

## Table of Contents

1. [Why This Project](#1-why-this-project)
2. [Architecture](#2-architecture)
3. [Syllabus Alignment](#3-syllabus-alignment)
4. [Tech Stack](#4-tech-stack)
5. [Project Structure](#5-project-structure)
6. [API Reference](#6-api-reference)
7. [Getting Started](#7-getting-started)
8. [Scope, Safety & Limitations](#8-scope-safety--limitations)
9. [Testing](#9-testing)
10. [Design Principles](#10-design-principles)
11. [Future Scope](#11-future-scope)

---

## 1. Why This Project

Most student AI projects pick one syllabus unit and build a demo around it — a search visualizer, a chatbot wrapper, a CNN classifier. RxLogic instead treats **medication scheduling** as a single problem that genuinely requires four different classical AI techniques to work together, with an LLM used only as an optional, replaceable input layer:

- **Knowledge representation & inference** — drug interactions as forward-chaining rules
- **Reasoning under uncertainty** — fuzzy logic over interaction confidence, not a binary flag
- **Constraint satisfaction** — dose timing as a CSP solved with backtracking + forward checking
- **Planning** — a goal-stack planner assembling the final schedule, risk-ordered

The litmus test for whether this is genuine neuro-symbolic AI rather than "LLM in, answer out": **disable the LLM and submit structured input via a plain form instead of free text — the system produces the exact same schedule, warnings, and explanations.** Only the natural-language convenience is lost. `services/reasoning_service.py` has zero import of, or dependency on, the LLM layer.

## 2. Architecture

RxLogic is layered so the symbolic reasoning core has no dependency on the neural layer — the LLM sits only at the input boundary, and everything downstream operates on strictly typed data.

```
                 ┌─────────────────────────────────────────────┐
                 │   Layer 1 · Interaction Layer (Neural)       │
                 │   services/llm_parser.py                     │
                 │   Free text ──(Ollama / phi3:mini)──▶ JSON   │
                 │   validated against the Medication schema    │
                 │   before it ever reaches the reasoning core  │
                 └───────────────────┬───────────────────────────┘
                                     │  typed Medication objects
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │   Layer 2 · Knowledge Layer (Symbolic)       │
                 │   knowledge/interaction_rules.json            │
                 │   services/drug_data_client.py                │
                 │   Curated interaction rules + cached RxNav /  │
                 │   openFDA lookups (RxCUI resolution)          │
                 └───────────────────┬───────────────────────────┘
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │   Layer 3 · Reasoning Core (Symbolic)        │
                 │   services/reasoning_service.py  (orchestrator)│
                 │                                                │
                 │   1. rule_engine.py    forward-chaining        │
                 │      → flags known interaction pairs           │
                 │   2. uncertainty.py    Mamdani fuzzy inference │
                 │      → refines each flag's confidence          │
                 │   3. planner.py        goal-stack planning     │
                 │      └─ csp_scheduler.py  backtracking + MRV   │
                 │         + forward checking → dose times        │
                 └───────────────────┬───────────────────────────┘
                                     │  DailyPlan (entries, warnings, goal_trace)
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │   Layer 4 · Application Layer                │
                 │   routes/api.py (Flask blueprint, rate-limited)│
                 │   frontend/ (React + Vite + Tailwind)          │
                 └───────────────────┬───────────────────────────┘
                                     ▼
                 ┌─────────────────────────────────────────────┐
                 │   Layer 5 · Persistence Layer                │
                 │   models/database.py · services/plan_log_service.py│
                 │   SQLite (dev/test) / PostgreSQL (prod)       │
                 │   Immutable, auditable log of every plan       │
                 └─────────────────────────────────────────────┘
```

**End-to-end data flow:**

1. User submits medications — either structured JSON (`POST /api/plan`) or free text (`POST /api/plan/nl`).
2. If free text: the LLM parser extracts a structured medication list and validates it against the schema.
3. The rule engine forward-chains over every medication pair, flagging known interactions.
4. The uncertainty layer refines each flagged interaction's confidence via fuzzy inference over severity and source reliability.
5. The CSP scheduler encodes dose timing, meal windows, and interaction-driven separation as constraints, and solves for a feasible schedule via backtracking search with MRV variable ordering and forward checking.
6. The planner resolves the goal stack (highest-severity medications committed first) against the CSP solution and records the resolution order.
7. The API serializes the plan and best-effort logs it to the database — a logging failure never turns a successful plan into a 500.
8. The response includes the schedule, every warning, and a full `goal_trace` — nothing is a black box.

## 3. Syllabus Alignment

| Unit | Topic Area | Where It Lives |
|---|---|---|
| 1 | Problem spaces, production systems | Scheduling framed as a state-space problem: state = current schedule, operators = placing/shifting a dose, goal test = zero conflicts |
| 2 | Search & CSP techniques | `services/csp_scheduler.py` — backtracking search, MRV heuristic, forward checking |
| 3 | Knowledge representation, forward chaining | `services/rule_engine.py` + `knowledge/interaction_rules.json` — curated predicate-style interaction facts, forward-chained per medication pair |
| 4 | Reasoning under uncertainty | `services/uncertainty.py` — Mamdani fuzzy inference system over severity and source reliability |
| 5 | Planning, goal-stack planning, intelligent agents | `services/planner.py` — goal-stack assembly, risk-ordered; the system as a whole follows perceive → reason → act → explain |

## 4. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language Understanding | Ollama + `phi3:mini` (local) | Free-text → structured data, entirely optional |
| Backend Framework | Flask 3 + Flask-Limiter | REST API, per-endpoint rate limiting |
| Symbolic Reasoning | Pure Python | Rule engine, CSP solver, goal-stack planner |
| Uncertainty Modeling | `scikit-fuzzy` | Mamdani fuzzy inference for interaction confidence |
| External Data | RxNav (NLM) + openFDA | RxCUI resolution and drug label data, cached locally |
| Persistence | SQLAlchemy 2 · SQLite (dev/test) / PostgreSQL via Neon (prod) | Immutable audit log of every generated plan |
| Frontend | React 18 + Vite + Tailwind CSS + React Router | Input form, schedule timeline, warnings panel, plan history |
| Testing | pytest + pytest-cov | Unit tests across every reasoning module and the API layer |
| Deployment | Render + Gunicorn | Single-service deployment — Flask serves the built React bundle, same-origin, no CORS |
| Version Control | Git + GitHub | Source control |

## 5. Project Structure

```
RxLogic-main/
├── app.py                       # Flask application factory
├── extensions.py                # Shared extension instances (rate limiter)
├── models/
│   ├── schemas.py                # Medication, Interaction, ScheduleEntry, DailyPlan
│   ├── exceptions.py             # Typed domain exceptions (fail-safe, never bare Exception)
│   └── database.py               # SQLAlchemy engine, PlanLog model
├── services/
│   ├── llm_parser.py             # NL → structured Medication (Ollama, optional)
│   ├── rule_engine.py            # Forward-chaining interaction detection
│   ├── uncertainty.py            # Fuzzy-logic confidence refinement
│   ├── csp_scheduler.py          # Dose-timing CSP: backtracking + MRV + forward checking
│   ├── planner.py                # Goal-stack planning → final DailyPlan
│   ├── reasoning_service.py      # Single orchestration entry point for the pipeline
│   ├── drug_data_client.py       # RxNav / openFDA client with local JSON caching
│   └── plan_log_service.py       # Typed objects ↔ persistence layer translation
├── routes/
│   └── api.py                    # Thin REST controllers, JSON ↔ typed schema boundary
├── knowledge/
│   ├── interaction_rules.json     # Curated interaction rule base + resolved RxCUIs
│   └── cache/                     # Cached RxNav/openFDA responses (regenerable)
├── scripts/
│   └── build_knowledge_base.py    # One-off script to resolve seed medications to RxCUIs
├── tests/                          # 10 test modules — every reasoning stage + API + DB
├── frontend/                       # React + Vite + Tailwind demo UI
│   └── src/
│       ├── components/             # MedicationForm, ScheduleTimeline, WarningsPanel, GoalTrace, Hero, NavBar
│       └── pages/                  # HomePage, HistoryPage
├── requirements.txt
└── Procfile                        # gunicorn app:app
```

## 6. API Reference

All routes are under `/api`, rate-limited per endpoint, and return a specific error code + message for every domain failure — never an unhandled 500 for a known failure mode.

| Endpoint | Method | Rate Limit | Purpose |
|---|---|---|---|
| `/api/health` | GET | — | Service health check |
| `/api/info` | GET | — | Service metadata |
| `/api/plan` | POST | 20/min | Structured medication list → full reasoning pipeline → `DailyPlan` |
| `/api/plan/nl` | POST | 10/min | Free-text description → LLM parse → identical reasoning pipeline |
| `/api/plans` | GET | 30/min | Most recent logged plans, newest first (`?limit=`, capped at 100) |

**Example — `POST /api/plan`:**

```json
{
  "medications": [
    { "name": "warfarin", "frequency_per_day": 1, "timing_preference": "morning" },
    { "name": "aspirin", "frequency_per_day": 1, "with_food": true }
  ]
}
```

Returns a chronologically ordered schedule, every flagged interaction with its severity and confidence, and a `goal_trace` showing the exact order in which medications were resolved.

**Error responses**, all `RxLogicError` subclasses mapped to specific HTTP codes:

| Error | Status | Cause |
|---|---|---|
| `schema_validation_error` | 400 | Malformed request body or LLM output that fails schema validation |
| `unknown_medication` | 422 | Medication can't be resolved against the knowledge base |
| `insufficient_data` | 422 | Empty medication list — nothing to reason about |
| `no_feasible_schedule` | 422 | CSP has no solution under the given constraints |
| `external_api_error` | 502 | RxNav / openFDA / Ollama call failed |

## 7. Getting Started

### Backend

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # serves on http://localhost:5000
```

By default the backend uses an in-memory SQLite database. To use PostgreSQL, set `DATABASE_URL` in `.env` (a Neon `postgres://` URL is normalized to `postgresql://` automatically).

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173, proxies /api to :5000
```

For a single deployable artifact, `npm run build` produces `frontend/dist/`, which `app.py` serves directly — no separate frontend host, no CORS configuration.

### Optional: natural-language input

Natural-language parsing (`/api/plan/nl`) requires a local [Ollama](https://ollama.com) instance:

```bash
ollama pull phi3:mini
ollama serve
```

If Ollama isn't running, `/api/plan/nl` returns a clean `external_api_error` — every other route, and the entire reasoning core, is unaffected. This is by design (see §1).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///:memory:` | Persistence backend |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `phi3:mini` | Local model used for NL parsing |
| `FLASK_DEBUG` | `false` | Flask debug mode — off by default in every environment |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `PORT` | `5000` | Server port |

## 8. Scope, Safety & Limitations

This section is treated as a first-class part of the system design, not an afterthought.

- **This is an educational demonstrator**, illustrating neuro-symbolic reasoning applied to a safety-adjacent domain. It is not a substitute for professional medical or pharmacist advice and is not intended for real-world medication decisions.
- The interaction rule base is **curated, not exhaustive** — it currently covers 12 rules across 10 seed medications ([`knowledge/interaction_rules.json`](knowledge/interaction_rules.json)) and does not account for patient-specific factors such as age, weight, renal or hepatic function, or pregnancy.
- **RxNav's live Drug-Drug Interaction API was discontinued by NLM in January 2024.** RxLogic only uses RxNav for RxCUI resolution (still live) and openFDA for label data; interaction *rules* themselves are manually curated, sourced from openFDA labeling and clinical literature, not pulled live.
- Unknown medications or insufficient rule coverage produce an explicit `insufficient_data` / `unknown_medication` response — **never a silent guess or false negative.**
- Every interaction warning and every scheduling decision is traceable to the specific rule or constraint that produced it (`rule_id`, `constraint_ids`, `goal_trace`) — the system's reasoning can be audited, not just trusted.
- A visible disclaimer should be shown in the application UI and stated upfront in any demo or presentation of this project.

## 9. Testing

```bash
pytest                            # run the full suite
pytest --cov=services --cov=models --cov=routes   # with coverage
```

Ten test modules cover the rule engine, uncertainty layer, CSP scheduler, planner, LLM parser, drug data client, database layer, API routes, and a full end-to-end pipeline run — each reasoning module is independently testable with zero dependency on the LLM or the API layer, matching the architectural separation above.

## 10. Design Principles

- **Strict schema boundary.** `models/schemas.py`'s frozen dataclasses are the *only* thing that crosses layer boundaries. The reasoning core never imports SQLAlchemy; the persistence layer never imports the reasoning core's types; the LLM never talks to the reasoning engine with raw text.
- **Fail-safe over confident-but-wrong.** Every failure mode — unknown medication, unsatisfiable constraints, malformed LLM output, empty input — raises a specific typed exception from `models/exceptions.py`, never a bare `Exception`.
- **No black-box output.** Every interaction is traceable to a `rule_id`; every dose placement carries `constraint_ids` and a human-readable `reasoning` string; every plan carries a `goal_trace` of the exact resolution order.
- **The LLM is provably optional.** Remove `services/llm_parser.py` entirely and `services/reasoning_service.py` still fully works via structured input — this is enforced by the module boundary, not just documentation.
- **Type hints, dataclasses, and named constants throughout** — no magic numbers, no untyped dicts passed between layers.

## 11. Future Scope

- Expand the knowledge base with a larger, clinician-reviewed interaction dataset.
- Add patient-specific parameters (age, weight, renal function) to the reasoning layer.
- Extend the fuzzy uncertainty layer into a full dynamic Bayesian network for time-varying risk as medications are added or removed.
- Add a notification/reminder subsystem for real adherence tracking (explicitly out of scope for this build).
- Explore a small fine-tuned or distilled model for the parsing layer to reduce local compute requirements.

---

**Author:** Raghav Shikriwal · B.Tech Information Technology, 3rd Year — NSUT
**Course Alignment:** Artificial Intelligence Elective