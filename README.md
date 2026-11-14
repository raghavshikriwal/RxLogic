
# RxLogic

### An Explainable Neuro-Symbolic Medication Reasoning and Scheduling System with Evidence-Governed Knowledge Management

<p align="center">
  <strong>Neuro-Symbolic AI · Constraint Satisfaction · Explainable Reasoning · Evidence Governance · Clinical Knowledge Management</strong>
</p>

<p align="center">
  <a href="https://github.com/raghavshikriwal/RxLogic/actions/workflows/tests.yml">
    <img src="https://github.com/raghavshikriwal/RxLogic/actions/workflows/tests.yml/badge.svg" alt="Tests">
  </a>
  <img src="https://img.shields.io/badge/Python-3.12-blue" alt="Python">
  <img src="https://img.shields.io/badge/React-18-61DAFB" alt="React">
  <img src="https://img.shields.io/badge/Flask-3.0-black" alt="Flask">
  <img src="https://img.shields.io/badge/Vite-6-646CFF" alt="Vite">
  <img src="https://img.shields.io/badge/Project%20Tasks-01--11-success" alt="Tasks 01–11">
  <img src="https://img.shields.io/badge/Status-Research%20Demonstrator-orange" alt="Research Demonstrator">
</p>

<p align="center">
  <a href="https://github.com/raghavshikriwal/RxLogic">GitHub Repository</a> ·
  <a href="https://rxlogic-ataf.onrender.com">Live Demonstration</a>
</p>

---

> **IMPORTANT MEDICAL AND SAFETY DISCLAIMER**
>
> RxLogic is an educational and software-engineering research demonstrator. It is NOT a medical device, has NOT been clinically validated, and is NOT authorized for patient-care use.
>
> It must not be used to diagnose conditions, prescribe medication, select treatments, calculate patient-specific dosages, determine whether a medication combination is safe, or make real medication decisions.
>
> The included knowledge base is limited and contains unreviewed development records. A missing warning or absent knowledge entry does not establish safety.
>
> Use synthetic demonstration data only. Consult a qualified healthcare professional for all real medication decisions.

---

# Table of Contents

1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Project Objectives](#3-project-objectives)
4. [Key Features](#4-key-features)
5. [System Architecture](#5-system-architecture)
6. [Core Reasoning Pipeline](#6-core-reasoning-pipeline)
7. [Major Algorithms and Methodologies](#7-major-algorithms-and-methodologies)
8. [Knowledge Base and Evidence Governance](#8-knowledge-base-and-evidence-governance)
9. [Task-by-Task Development History](#9-task-by-task-development-history)
10. [Medication Catalog and Knowledge Coverage](#10-medication-catalog-and-knowledge-coverage)
11. [Task 09 Clinical Reasoning Integration](#11-task-09-clinical-reasoning-integration)
12. [Application Walkthrough](#12-application-walkthrough)
13. [API Documentation](#13-api-documentation)
14. [Technology Stack](#14-technology-stack)
15. [Project Structure](#15-project-structure)
16. [Installation and Setup](#16-installation-and-setup)
17. [Running the Application](#17-running-the-application)
18. [Configuration](#18-configuration)
19. [Testing and Verification](#19-testing-and-verification)
20. [Knowledge Management Workflows](#20-knowledge-management-workflows)
21. [Deployment](#21-deployment)
22. [Security and Privacy](#22-security-and-privacy)
23. [Known Limitations](#23-known-limitations)
24. [Future Scope](#24-future-scope)
25. [Evaluation and Viva Preparation](#25-evaluation-and-viva-preparation)
26. [Conclusion](#26-conclusion)
27. [License](#27-license)

---

# 1. Project Overview

**RxLogic** is a full-stack neuro-symbolic medication-reasoning and scheduling demonstrator designed to explore how natural-language processing, deterministic rule-based reasoning, fuzzy logic, constraint satisfaction, and evidence-governed knowledge management can work together within a single software architecture.

The project combines the flexibility of an optional Large Language Model (LLM) input layer with the transparency and predictability of symbolic reasoning.

Rather than allowing an LLM to independently determine medication interactions or produce schedules, RxLogic separates language understanding from downstream decision logic.

The application transforms structured or natural-language input into validated domain objects, evaluates configured knowledge rules, refines uncertainty representations, constructs scheduling constraints, and generates explainable software outputs.

Beyond its reasoning pipeline, RxLogic implements a controlled knowledge lifecycle that separates external evidence collection from clinical knowledge approval and runtime publication.

The knowledge-management architecture includes:

- Evidence ingestion and source preservation.
- Cryptographic content-integrity verification.
- Evidence inspection and reviewer decisions.
- Evidence-linked knowledge candidates.
- Independent clinical review.
- Conflict assessment.
- Immutable knowledge releases.
- Explicit release promotion and rollback.
- Integrity-checked runtime loading.
- Audit trails for knowledge-management operations.

The development has progressed through eleven major implementation tasks, integrating the backend, frontend, reasoning services, medication catalog, knowledge governance, testing infrastructure, and clinical-assessment response architecture.

## Current Project Status

**Task 11 status:** the dual-control release-governance implementation is prepared on the `task-11-knowledge-governance` branch. The focused release/CLI/clinical-knowledge/audit suite passed 46 tests in the implementation environment. Run the full Windows suite before treating Task 11 as finally accepted.


| Component | Status |
|---|---|
| Tasks 01–09 | Implemented and integrated |
| Task 10 clinical validation framework | Implemented; clinical validation itself not performed |
| Task 11 release governance | Implemented on `task-11-knowledge-governance`; full Windows regression pending |
| Backend | Implemented |
| React frontend | Implemented |
| Neuro-symbolic reasoning | Implemented |
| Constraint-based scheduling | Implemented |
| Fuzzy confidence refinement | Implemented |
| Goal-stack planning | Implemented |
| Medication identity catalog | Implemented |
| Evidence ingestion | Implemented |
| Evidence review workflow | Implemented |
| Controlled knowledge releases | Implemented |
| Task 09 clinical assessment | Integrated |
| Task 10 Windows regression suite | 384 tests passed (pre-Task 11 snapshot) |
| Task 11 focused governance suite | 46 tests passed in implementation environment |
| Task 11 full regression suite | Pending Windows verification |
| Frontend production build | Passed |
| npm dependency audit | 0 vulnerabilities reported |
| Knowledge structural validation | Passed |
| Clinical validation | Not performed |
| Patient-care authorization | Not authorized |

**Latest recorded `main`-branch commit before Tasks 10–11 work:**

```text
217a7f9 Update README with complete project documentation
```

Task 10 and Task 11 changes are being prepared on a separate working branch and are not yet merged into `main`.

Repository:

https://github.com/raghavshikriwal/RxLogic

Branch:

```text
main
```

---

# 2. Problem Statement

Medication-related software involves several interconnected information-processing challenges.

These include:

- Medication-name ambiguity.
- Incomplete or inconsistent knowledge.
- Potential interactions between medications.
- Food-related constraints.
- Uncertainty in available evidence.
- Scheduling conflicts.
- Conflicting or outdated source information.
- The need for traceable and explainable outputs.

A conventional application may rely on fixed lookup tables, while an LLM-based application may generate plausible but unsupported information.

RxLogic explores a different approach.

It separates input interpretation, knowledge evaluation, constraint solving, planning, and evidence governance into distinct software components.

The central engineering problem is:

**How can an AI-assisted medication-reasoning system combine flexible input interpretation with deterministic, inspectable decision logic and a controlled knowledge lifecycle?**

RxLogic approaches this problem using a modular neuro-symbolic architecture.

---

# 3. Project Objectives

The main objectives are:

1. Develop a modular medication-reasoning application.
2. Integrate an optional natural-language parsing layer.
3. Convert input into validated structured medication objects.
4. Implement deterministic medication-rule evaluation.
5. Represent uncertainty using fuzzy reasoning.
6. Develop a constraint-satisfaction scheduling engine.
7. Implement goal-stack planning.
8. Provide explainable outputs and reasoning traces.
9. Maintain a structured medication identity catalog.
10. Separate evidence collection from knowledge approval.
11. Preserve source provenance and content integrity.
12. Implement independent clinical-review requirements for clinical assertions.
13. Support immutable knowledge releases and explicit promotion.
14. Integrate governed clinical assertions into the Task 09 API response.
15. Build a responsive React frontend.
16. Establish regression tests and structural acceptance audits.
17. Maintain an evaluation-ready development and documentation process.

---

# 4. Key Features

## 4.1 Medication Identity and Name Normalization

RxLogic includes a medication identity catalog and normalization service.

Capabilities include:

- Canonical medication names.
- Explicit aliases.
- Guarded fuzzy matching.
- Medication identity metadata.
- RxNorm/RxCUI identifiers where registered.
- Unknown-name handling.
- Normalization explanations.

For example:

```text
paracetamol
     |
     v
acetaminophen
```

The catalog recognizes `paracetamol` as an alias for `acetaminophen`.

This is a terminology-resolution capability only. It does not establish clinical interaction coverage, dosing instructions, contraindications, or medication suitability.

## 4.2 Symbolic Interaction Reasoning

The symbolic rule engine evaluates configured medication-pair rules.

It provides:

- Structured rule evaluation.
- Rule identifiers.
- Evidence metadata.
- Severity representation.
- Evidence-strength representation.
- Explicit handling of unavailable knowledge.

Severity and evidence strength are separate concepts.

A severe potential interaction and the strength of evidence supporting a rule are not interchangeable measurements.

## 4.3 Fuzzy Logic and Uncertainty Refinement

The uncertainty component demonstrates fuzzy reasoning using configured evidence-related inputs.

It helps represent graded confidence rather than relying exclusively on binary values.

Important distinction:

The generated confidence values are software representations based on development rules. They are not clinically calibrated probabilities.

## 4.4 Constraint-Satisfaction Scheduling

The scheduling engine formulates schedule generation as a constraint-satisfaction problem.

It uses:

- Variables and domains.
- Constraint propagation.
- Backtracking.
- Minimum Remaining Values (MRV).
- Forward checking.
- Scheduling-window constraints.
- Dose-spacing constraints.
- Meal-window constraints where applicable.

The scheduler searches for a feasible assignment under the configured constraints.

If no valid assignment exists, the system can return an explicit infeasibility result rather than inventing a schedule.

## 4.5 Goal-Stack Planning

RxLogic includes a goal-stack planning component.

It resolves scheduling goals through an explicit planning sequence and can expose a trace of goal resolution.

This provides an additional explanation layer beyond simply displaying a final schedule.

## 4.6 Optional Natural-Language Input

The application supports an optional Ollama-powered natural-language parsing workflow.

Example placeholder:

```text
Create a demonstration plan using the configured
synthetic medication inputs.
```

The parser extracts candidate structured fields.

The resulting data still passes through validation and the symbolic pipeline.

The LLM is not responsible for:

- Establishing clinical truth.
- Approving evidence.
- Deciding interaction severity.
- Publishing knowledge.
- Independently constructing the final schedule.

Structured input remains available without an LLM.

## 4.7 Evidence-Governed Knowledge Management

The project implements a controlled workflow for transforming source material into governed knowledge.

The stages are:

```text
Source acquisition
       |
       v
Evidence staging
       |
       v
Integrity verification
       |
       v
Evidence inspection
       |
       v
Reviewer decision
       |
       v
Knowledge candidate creation
       |
       v
Independent clinical review
       |
       v
Conflict assessment
       |
       v
Immutable release assembly
       |
       v
Explicit promotion
       |
       v
Runtime integrity verification
```

Evidence acceptance does not automatically mean clinical approval.

Release creation does not automatically mean release activation.

## 4.8 Task 09 Clinical Assessment

Task 09 adds an evidence-governed clinical-assessment component to the plan response.

It supports optional context fields:

- Foods.
- Conditions.

The assessment evaluates eligible assertions against explicitly supplied context.

It does not infer diagnoses or generate patient-specific dosage instructions.

Unapproved, rejected, withdrawn, unresolved-conflict, or otherwise ineligible assertions are excluded from findings.

Missing knowledge is represented as unavailable or insufficient rather than as proof of safety.

---

# 5. System Architecture

RxLogic uses a layered full-stack architecture.

```text
                  REACT + VITE FRONTEND
       -------------------------------------------
       Plan Form | Clinical Assessment | Warnings
       Schedule | Coverage | History
       -------------------------------------------
                         |
                         | HTTP / JSON
                         v
                    FLASK REST API
       -------------------------------------------
       Request Validation | Error Handling
       Session Management | Response Serialization
       -------------------------------------------
                         |
             -------------------------
             |                       |
             v                       v
       OPTIONAL LLM             STRUCTURED INPUT
       Ollama Parser             Direct Form Input
             |                       |
             -----------+-------------
                        |
                        v
                DOMAIN VALIDATION
       -------------------------------------------
       Typed Medication Objects
       Request Schemas
       Domain Constraints
       -------------------------------------------
                        |
                        v
              SYMBOLIC REASONING PIPELINE
       -------------------------------------------
       Name Normalization
              |
       Food Rule Evaluation
              |
       Interaction Rule Engine
              |
       Fuzzy Confidence Refinement
              |
       CSP Scheduler
              |
       Goal-Stack Planner
              |
       Explanation Generation
       -------------------------------------------
                        |
             -------------------------
             |                       |
             v                       v
       PLAN PERSISTENCE       CLINICAL ASSESSMENT
       History Records        Task 09 Integration
                                     |
                                     v
                          GOVERNED ASSERTIONS
                          Evidence-Linked Knowledge

       SEPARATE KNOWLEDGE GOVERNANCE SYSTEM
       -------------------------------------------
       Source Connectors
              |
       Evidence Ingestion
              |
       Evidence Review
              |
       Candidate Curation
              |
       Independent Approval
              |
       Immutable Release
              |
       Promotion / Rollback
              |
       Integrity-Checked Runtime
       -------------------------------------------
```

## Architectural Principles

### Separation of concerns

Each component has a defined responsibility.

### Deterministic downstream reasoning

The optional LLM does not replace the symbolic reasoning system.

### Explicit domain boundaries

Input is validated before it reaches the reasoning services.

### Explainability

Outputs can retain references to rules, evidence, constraints, and planning decisions.

### Knowledge governance

External information is not automatically trusted as runtime knowledge.

### Fail-closed behavior

Active-release mode refuses to silently use an invalid or missing approved release.

---

# 6. Core Reasoning Pipeline

The core pipeline follows a sequence of processing stages.

## Stage 1: Input Validation

The API receives structured or parsed input.

Request validation ensures that accepted values satisfy the defined schemas.

## Stage 2: Name Normalization

Medication names are checked against:

- Canonical names.
- Explicit aliases.
- Guarded fuzzy matching.

Unknown names are handled explicitly.

## Stage 3: Food-Rule Handling

The food-rule service checks configured guidance.

An important safety gate was introduced during Task 09:

Rules that are not explicitly marked approved are informational only and must not modify the medication's scheduling constraints.

## Stage 4: Interaction Evaluation

The symbolic rule engine evaluates configured medication-pair knowledge.

Results retain available rule and evidence metadata.

## Stage 5: Uncertainty Refinement

The fuzzy reasoning layer refines confidence representations using configured evidence-related information.

## Stage 6: Constraint Construction

The scheduler constructs variables, domains, and constraints.

## Stage 7: Constraint Solving

The CSP engine searches for a feasible schedule using propagation and backtracking.

## Stage 8: Goal-Stack Planning

The planner resolves the configured scheduling goals and records its execution trace.

## Stage 9: Clinical Assessment

Task 09 evaluates eligible evidence-governed assertions against explicitly supplied context.

## Stage 10: Response Generation

The API returns structured outputs containing available:

- Schedule entries.
- Warnings.
- Food guidance.
- Name normalization information.
- Knowledge coverage.
- Planning traces.
- Clinical assessment information.

---

# 7. Major Algorithms and Methodologies

| Methodology | Purpose |
|---|---|
| Rule-based reasoning | Deterministic evaluation of configured knowledge |
| Fuzzy logic | Graded confidence representation |
| Constraint Satisfaction Problem | Schedule construction |
| Backtracking | Search for feasible assignments |
| MRV heuristic | Select the most constrained variable |
| Forward checking | Detect domain conflicts early |
| Goal-stack planning | Resolve goals in an explicit sequence |
| SHA-256 | Source and dataset integrity verification |
| Immutable release manifests | Bind released knowledge to content hashes |
| Hash-linked audit events | Detect modification of promotion history |

## 7.1 Constraint Satisfaction

A scheduling problem can be represented as:

```text
CSP = (X, D, C)
```

Where:

- `X` represents scheduling variables.
- `D` represents possible time assignments.
- `C` represents scheduling constraints.

The scheduler searches for an assignment satisfying the configured constraints.

## 7.2 MRV

Minimum Remaining Values selects the variable with the smallest remaining domain.

This helps prioritize the most constrained scheduling decisions.

## 7.3 Forward Checking

After an assignment, forward checking removes incompatible values from neighboring variable domains.

If a domain becomes empty, the current search branch is rejected.

## 7.4 Backtracking

Backtracking explores alternative assignments when a constraint conflict is encountered.

It allows the solver to recover from unsuccessful partial assignments.

## 7.5 Evidence Integrity

The evidence workflow uses SHA-256 fingerprints to detect changes in source bytes and normalized payloads.

Integrity verification establishes whether stored content matches its recorded fingerprint. It does not establish that the source is medically correct.

---

# 8. Knowledge Base and Evidence Governance

Knowledge governance is one of the central engineering components of RxLogic.

## 8.1 Evidence Ingestion

The ingestion layer supports source staging and metadata validation.

It includes:

- Source identifiers.
- Publisher metadata.
- Source titles.
- Jurisdiction metadata.
- Canonical URLs.
- Original source bytes.
- Normalized payloads.
- Integrity fingerprints.

## 8.2 Source Connectors

The project includes bounded connectors for:

- RxNav/RxNorm.
- openFDA drug-label information.
- DailyMed SPL search.

Retrieved information is staged for review.

It is not automatically inserted into approved runtime knowledge.

## 8.3 Evidence Review

The evidence-review subsystem provides:

- Review queues.
- Evidence inspection.
- Hash verification.
- Reviewer decisions.
- Append-only decision records.

Accepted evidence is eligible for controlled curation, not automatic clinical publication.

## 8.4 Knowledge Curation

Candidate records are linked to evidence identifiers.

Clinical assertions require independent review by a qualified clinical reviewer, such as a physician or clinical pharmacist.

The candidate author cannot approve their own clinical candidate.

Conflicts must be assessed explicitly.

## 8.5 Immutable Knowledge Releases

A release contains a manifest binding datasets to content hashes.

The workflow distinguishes:

1. Candidate creation.
2. Candidate approval.
3. Release assembly.
4. Release promotion.
5. Runtime loading.

## 8.6 Promotion and Rollback

Promotion and rollback are separate audited operations.

The system records promotion events in a hash-linked event chain.

## 8.7 Active Release Integrity

In `active_release` mode, runtime loading verifies:

- Active release state.
- Manifest integrity.
- Dataset hashes.
- Schema validity.
- Audit-chain state.

If a valid active release is unavailable, the system fails closed.

It does not silently fall back to mutable development knowledge.

---

# 9. Task-by-Task Development History

The project was developed through nine staged implementation tasks.

## Task 01 — Repository Audit and Foundation

Established the initial engineering baseline.

Key work:

- Repository inventory.
- Architecture inspection.
- Initial knowledge review.
- Identification of technical gaps.
- Development roadmap.
- Initial documentation and audit artifacts.

## Task 02 — Knowledge Structure and Validation

Established structured knowledge representation.

Key work:

- Knowledge manifest.
- Evidence-source registry.
- Versioned schemas.
- Stable identifiers.
- Structural validation.
- Knowledge consistency checks.

## Task 03 — Evidence Ingestion

Implemented evidence staging and integrity controls.

Key work:

- Source metadata validation.
- HTTPS source restrictions.
- Evidence identifiers.
- Content-addressed staging.
- SHA-256 fingerprints.
- Ingestion command-line workflow.

## Task 04 — Official Source Connectors

Added bounded external-source integration.

Key work:

- RxNav/RxNorm connector.
- openFDA connector.
- DailyMed SPL search connector.
- Source retrieval and staging.
- External response handling.
- Provenance retention.

## Task 05 — Evidence Review and Inspection

Introduced a controlled evidence-review workflow.

Key work:

- Original source-byte preservation.
- Separate source and normalized-payload hashes.
- Evidence inspection.
- Review queue.
- Append-only reviewer decisions.
- Review CLI.

Accepted evidence remains staged for curation and is not automatically promoted.

## Task 06 — Controlled Knowledge Curation and Release Management

Implemented the controlled lifecycle between reviewed evidence and runtime knowledge.

Key work:

- Evidence-linked candidates.
- Candidate validation.
- Independent review.
- Immutable release assembly.
- Release manifests.
- Explicit promotion.
- Rollback.
- Runtime release loading.
- Integrity verification.
- Tamper-evident promotion event chain.

The Task 06 full regression suite was reported at 337 passing tests.

## Task 07 — Clinical Knowledge Expansion and Governance

Expanded the knowledge architecture with additional clinical assertion families.

Key work:

- Drug–food/component interaction assertions.
- Contraindication assertions.
- Dosage-reference assertions.
- Administration-instruction assertions.
- Evidence-quality appraisal.
- Conflict assessment.
- Independent clinical approval.
- Expanded governance and audit checks.

The Task 07 full regression suite was reported at 358 passing tests.

## Task 08 — Medication Identity and Knowledge Coverage

Expanded medication identity and coverage reporting.

Key work:

- Versioned medication catalog.
- Canonical identity records.
- RxNorm/RxCUI metadata.
- Alias handling.
- Paracetamol-to-acetaminophen normalization.
- Catalog consistency validation.
- Medication coverage auditing.
- Expanded acceptance reporting.

The Task 08 full regression suite was reported at 366 passing tests.

## Task 09 — Clinical Reasoning Integration

Integrated governed clinical assertions into the application response.

Key work:

- Clinical assessment service.
- Explicit food and condition context.
- Evidence-governed assertion matching.
- Exclusion of unapproved assertions.
- Exclusion of unresolved conflicts.
- Non-prescriptive dosage handling.
- Assessment API response.
- Frontend clinical-assessment component.
- Regression tests.
- Task 09 acceptance audit.

The Task 09 full regression suite was reported at **377 passing tests**.

The current Task 09 structural audit reports zero approved runtime clinical assertions. This means the application must not invent clinical findings when no approved assertion is available.

## Task 10 — Clinical Validation and Reliability Framework

Added a structured framework for future independent clinical-reference evaluation and software safety invariants.

Key work:

- Versioned clinical validation case registry, intentionally empty by default.
- Two-reviewer decision and independent-adjudication requirements.
- Reviewer agreement and Cohen's kappa reporting.
- Confusion-matrix and binary metric calculations with undefined values represented as `null`.
- Runtime probes for fail-closed behavior, missing knowledge, and non-patient-specific dosage handling.
- Task 10 acceptance audit and validation protocol.

The user-reported Windows Task 10 full regression suite passed **384 tests**. This is software test evidence only. No clinical reference cases were supplied, so clinical validation remains `not_performed` and clinical performance metrics are unavailable.

## Task 11 — Release Governance and Dual Control

Strengthened the existing immutable-release workflow with independent release-level approval and promotion separation.

Key work:

- Versioned release-governance policy.
- Release manifest context recording creator, candidate authors, and candidate-level clinical approvers.
- Separate clinical-release and governance-release approvals.
- Reviewer-role constraints and independent reviewer identities.
- Promoter separation from all authors and reviewers.
- Append-only SHA-256 hash-chained release-review log bound to the exact manifest hash.
- Active-pointer and promotion-event binding to the release-review digest.
- Runtime verification of current dual-control approvals.
- Required rollback rationale and renewed evidence/approval checks.
- `release-review` and `review-status` CLI commands.
- Task 11 governance acceptance audit.

The focused Task 11 release/CLI/clinical-knowledge/audit suite passed **46 tests** in the implementation environment. The full project regression suite must still be run on Windows before final acceptance. Reviewer IDs and roles are local CLI declarations, not authenticated identities or verified credentials.

---

# 10. Medication Catalog and Knowledge Coverage

The medication catalog is a structured identity resource.

It is not a comprehensive medication database.

The current Task 08 development inventory reported:

| Metric | Reported count |
|---|---:|
| Medication identities | 11 |
| Possible unordered medication pairs | 55 |
| Legacy DDI assertions present but unreviewed | 12 |
| DDI pairs not evaluated | 43 |
| Legacy meal-guidance entries present but unreviewed | 4 |
| Medication entries without meal-guidance assessment | 7 |

These counts describe the development snapshot and its audit output.

They do not represent complete clinical coverage.

## 10.1 Paracetamol Support

The catalog registers:

```text
Canonical identity: acetaminophen
RxNorm concept: 161
Alias: paracetamol
```

A test with `paracetamol` can demonstrate name normalization.

It cannot demonstrate that the application has clinically approved interaction, contraindication, food, or dosage knowledge for that medication.

## 10.2 Coverage Interpretation

The application distinguishes:

- Recognized identity.
- Evaluated knowledge.
- Unreviewed knowledge.
- Approved knowledge.
- Missing knowledge.

These categories must not be collapsed into a single safety indicator.

In particular:

**Not evaluated does not mean no interaction.**

**No warning does not mean safe.**

---

# 11. Task 09 Clinical Reasoning Integration

Task 09 introduces a clinical-assessment response layer.

Its responsibility is to expose eligible governed knowledge in a structured API response.

## 11.1 Supported Context

The optional context object supports:

```json
{
  "patient_context": {
    "foods": [],
    "conditions": []
  }
}
```

The arrays contain explicitly supplied non-empty strings when used.

Matching is exact and case-insensitive.

The application does not infer medical conditions.

## 11.2 Assertion Eligibility

Clinical findings are restricted to assertions satisfying the configured governance requirements.

Assertions that are:

- Unreviewed.
- Rejected.
- Withdrawn.
- Conflict-unassessed.
- In unresolved conflict.

are excluded from findings.

## 11.3 Dosage Handling

Dosage references are treated as source-backed reference records.

They are not transformed into patient-specific dosing instructions.

## 11.4 Privacy Boundary

Task 09 patient context and context-derived assessment findings are not persisted in plan-history records.

## 11.5 Current Approval State

The latest Task 09 audit reports:

| Assertion domain | Total assertions | Approved and conflict-assessed |
|---|---:|---:|
| Drug–food interactions | 0 | 0 |
| Contraindications | 0 | 0 |
| Dosage references | 0 | 0 |
| Administration instructions | 0 | 0 |
| **Total** | **0** | **0** |

The correct interpretation is that no approved runtime clinical findings are currently available from these four assertion domains.

---

# 12. Application Walkthrough

## 12.1 Plan Page

The Plan page provides structured and optional natural-language input.

Structured fields can include:

- Medication name.
- Dosage field.
- Frequency.
- Timing preference.
- Food preference.

The exact accepted values are controlled by the backend schemas.

## 12.2 Schedule Results

The result view can display:

- Generated schedule.
- Dose-time entries.
- Scheduling warnings.
- Rule explanations.
- Name normalization.
- Food guidance.
- Knowledge coverage.
- Goal-stack trace.

## 12.3 Clinical Assessment

The Task 09 frontend component displays available clinical-assessment information, including:

- Assessment status.
- Eligible findings.
- Knowledge availability.
- Excluded assertions.
- Conflict information.
- Evidence references.
- Non-prescriptive limitations.

## 12.4 History

The History page displays available saved plan records.

Task 09 patient context and context-derived assessment findings are excluded from plan-history persistence.

## 12.5 Safe Demonstration

A software demonstration can use synthetic medication entries to show:

1. Structured input.
2. Name normalization.
3. Rule evaluation.
4. Knowledge coverage.
5. Scheduling behavior.
6. Planning traces.
7. Clinical-assessment status.
8. Evidence-governance workflows.

Do not use real patient medication regimens.

---

# 13. API Documentation

All API endpoints are under:

```text
/api
```

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/info` | GET | Application information |
| `/api/plan` | POST | Structured plan generation |
| `/api/plan/nl` | POST | Natural-language plan generation |
| `/api/plans` | GET | Retrieve available plan history |
| `/api/knowledge/status` | GET | Knowledge and active-release status |

## 13.1 Structured Plan Request

Illustrative request structure:

```json
{
  "medications": [
    {
      "name": "example-supported-name",
      "frequency_per_day": 1,
      "timing_preference": "no_preference"
    }
  ]
}
```

The values are placeholders, not medication instructions.

## 13.2 Context-Aware Plan Request

```json
{
  "medications": [
    {
      "name": "example-supported-name",
      "frequency_per_day": 1
    }
  ],
  "patient_context": {
    "foods": [
      "example-food"
    ],
    "conditions": [
      "example-condition"
    ]
  }
}
```

## 13.3 Clinical Assessment Response

The Task 09 response includes a `clinical_assessment` object.

Its information can include:

- Overall assessment status.
- Findings.
- Per-domain knowledge availability.
- Excluded assertion counts.
- Conflict information.
- Evidence provenance.
- Dosage-reference safety metadata.
- `clinical_use_permitted: false`.

## 13.4 Error Handling

Representative error categories include:

| Error | Meaning |
|---|---|
| `schema_validation_error` | Invalid request |
| `unknown_medication` | Unsupported medication identity |
| `insufficient_data` | Missing usable input |
| `no_feasible_schedule` | Scheduling constraints cannot be satisfied |
| `external_api_error` | External source request failed |
| `llm_api_error` | Natural-language service failed |
| Knowledge-release error | Active release unavailable or integrity verification failed |

For exact schemas and response structures, refer to:

```text
models/schemas.py
routes/api.py
docs/TASK_09_API_CONTRACT.md
```

---

# 14. Technology Stack

| Category | Technology |
|---|---|
| Programming language | Python 3.12 |
| Frontend framework | React 18 |
| Frontend build tool | Vite 6 |
| Styling | Tailwind CSS 3 |
| Client routing | React Router 7 |
| Backend framework | Flask 3 |
| API rate limiting | Flask-Limiter |
| Language model integration | Ollama |
| Default local LLM | phi3:mini |
| Domain modeling | Python dataclasses and enums |
| Rule reasoning | Custom Python rule engine |
| Fuzzy logic | scikit-fuzzy |
| Scheduling | CSP and backtracking |
| Planning | Goal-stack planner |
| Persistence | SQLAlchemy 2 |
| Database migrations | Alembic |
| Development database | SQLite |
| Production database option | PostgreSQL |
| Testing | pytest |
| Coverage | pytest-cov |
| Source integrity | SHA-256 |
| External sources | RxNav/RxNorm, openFDA, DailyMed |
| Application server | Gunicorn |
| Deployment | Render |
| CI/CD | GitHub Actions |

---

# 15. Project Structure

```text
RxLogic/
│
├── app.py
├── extensions.py
├── requirements.txt
├── runtime.txt
├── Procfile
├── .env.example
├── alembic.ini
│
├── routes/
│   └── api.py
│
├── models/
│   ├── schemas.py
│   ├── exceptions.py
│   └── database.py
│
├── services/
│   ├── llm_parser.py
│   ├── name_normalizer.py
│   ├── medication_catalog.py
│   ├── drug_data_client.py
│   ├── medical_source_client.py
│   ├── evidence_ingestion.py
│   ├── evidence_review.py
│   ├── knowledge_curation.py
│   ├── knowledge_release.py
│   ├── knowledge_validation.py
│   ├── clinical_validation.py
│   ├── task10_audit.py
│   ├── task11_audit.py
│   ├── clinical_knowledge.py
│   ├── clinical_reasoning.py
│   ├── food_rules.py
│   ├── rule_engine.py
│   ├── uncertainty.py
│   ├── csp_scheduler.py
│   ├── planner.py
│   ├── reasoning_service.py
│   └── plan_log_service.py
│
├── knowledge/
│   ├── manifest.json
│   ├── medication_catalog.json
│   ├── drug_aliases.json
│   ├── interaction_rules.json
│   ├── food_rules.json
│   ├── clinical_assertions.json
│   ├── evidence_sources.json
│   ├── release_governance_policy.json
│   ├── release_review_events.jsonl (created when reviews are recorded)
│   ├── ingestion/
│   ├── staging/
│   ├── curation/
│   └── releases/
│
├── scripts/
│   ├── ingest_evidence.py
│   ├── review_evidence.py
│   ├── fetch_medical_source.py
│   ├── manage_knowledge.py
│   ├── audit_knowledge_coverage.py
│   ├── audit_medication_catalog.py
│   ├── audit_task07.py
│   ├── audit_task08.py
│   ├── audit_task09.py
│   ├── audit_task10.py
│   └── audit_task11.py
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── api.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── dist/
│   ├── package.json
│   └── vite.config.js
│
├── tests/
│   └── test_*.py
│
├── docs/
│   ├── TASK_01_CHANGELOG.md
│   ├── TASK_01_REPOSITORY_AUDIT.md
│   ├── TASK_02_CHANGELOG.md
│   ├── TASK_03_CHANGELOG.md
│   ├── TASK_04_CHANGELOG.md
│   ├── TASK_05_CHANGELOG.md
│   ├── TASK_06_CHANGELOG.md
│   ├── TASK_06_STAGE_5_ACCEPTANCE_AUDIT.md
│   ├── TASK_07_CHANGELOG.md
│   ├── TASK_07_ACCEPTANCE_AUDIT.md
│   ├── TASK_08_CHANGELOG.md
│   ├── TASK_08_ACCEPTANCE_AUDIT.md
│   ├── TASK_09_CHANGELOG.md
│   ├── TASK_09_API_CONTRACT.md
│   ├── TASK_10_CHANGELOG.md
│   ├── TASK_10_VALIDATION_PROTOCOL.md
│   ├── TASK_11_CHANGELOG.md
│   ├── TASK_11_RELEASE_GOVERNANCE_PROTOCOL.md
│   └── TASK_11_ACCEPTANCE_AUDIT.md
│
├── reports/
│   ├── knowledge_coverage.json
│   ├── medication_catalog_audit.json
│   ├── task07_acceptance_audit.json
│   ├── task08_acceptance_audit.json
│   ├── task09_acceptance_audit.json
│   ├── task10_acceptance_audit.json
│   └── task11_acceptance_audit.json
│
└── .github/
    └── workflows/
        └── tests.yml
```

The structure is representative. Some local generated artifacts, staging files, databases, caches, and environment-specific files may not be shown.

---

# 16. Installation and Setup

## 16.1 Prerequisites

Install:

- Python 3.12.
- Node.js 20 or later.
- npm.
- Git.

Ollama is optional and required only for local natural-language mode.

## 16.2 Clone the Repository

```powershell
git clone https://github.com/raghavshikriwal/RxLogic.git

cd RxLogic
```

## 16.3 Create Python Virtual Environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv

.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip

python -m pip install -r requirements.txt
```

If PowerShell blocks activation:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 16.4 Configure Environment

```powershell
Copy-Item .env.example .env
```

Do not commit `.env` or any secrets.

## 16.5 Install Frontend Dependencies

```powershell
cd frontend

npm ci

cd ..
```

---

# 17. Running the Application

## 17.1 Start Backend

From the repository root:

```powershell
python app.py
```

The development backend normally runs at:

```text
http://127.0.0.1:5000
```

## 17.2 Start Frontend

Open a second terminal:

```powershell
cd frontend

npm run dev
```

Open the Vite URL printed in the terminal.

The frontend development configuration proxies API requests to Flask.

## 17.3 Production Frontend Build

```powershell
cd frontend

npm run build

cd ..
```

The generated production frontend is stored in:

```text
frontend/dist/
```

## 17.4 Optional Ollama Setup

Install Ollama separately.

Pull the configured model:

```powershell
ollama pull phi3:mini
```

Check installed models:

```powershell
ollama list
```

Start Ollama if it is not already running:

```powershell
ollama serve
```

Natural-language mode requires a reachable local Ollama service.

Structured input does not require an LLM.

---

# 18. Configuration

The reference configuration is maintained in `.env.example`.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Database connection |
| `OLLAMA_BASE_URL` | Local Ollama endpoint |
| `OLLAMA_MODEL` | Local model identifier |
| `LOG_LEVEL` | Logging level |
| `FLASK_DEBUG` | Development debug mode |
| `PORT` | Application port |
| `RXLOGIC_KNOWLEDGE_MODE` | Knowledge loading mode |
| `RXLOGIC_KNOWLEDGE_ROOT` | Optional knowledge-root override |

## Knowledge Modes

### legacy_development

Uses the repository's development knowledge files.

This mode is intended for backwards-compatible development and demonstration.

The legacy knowledge is not clinically reviewed.

### active_release

Uses the explicitly promoted, integrity-verified knowledge release.

The runtime does not silently fall back to mutable development JSON when the active release is missing or invalid.

**Current status:** No valid active approved release is configured in the latest reported Task 09 snapshot.

Enabling this mode without a valid promoted release is expected to fail closed.

---

# 19. Testing and Verification

Testing is performed at multiple levels.

## 19.1 Latest Full Python Regression Suite

The latest user-reported Windows full-suite run before Task 11 reported:

```text
384 passed
0 failed
109.29 seconds
```

That result corresponds to the Task 10 snapshot, before the Task 11 release-governance changes. Run the full suite again on the Task 11 branch.

Command:

```powershell
python -m pytest -q
```

## 19.2 Historical Test Milestones

| Project snapshot | Reported result |
|---|---:|
| Task 06 | 337 passed |
| Task 07 | 358 passed |
| Task 08 | 366 passed |
| Task 09 | 377 passed |
| Task 10 | **384 passed** |
| Task 11 focused release/CLI/clinical-knowledge/audit suite | **46 passed** (implementation environment; not full-suite total) |

These are historical suite totals from different project snapshots. They must not be added together.

The Task 10 result is the latest user-reported full-suite result. Task 11 has not yet received a full Windows regression run.

## 19.3 Task 11 Implementation-Environment Verification

The Task 11-focused release, CLI, clinical-knowledge, and audit subset reported **46 passed**. A broader dependency-available subset reported **307 passed**; this deliberately excluded test modules whose runtime dependencies (`flask`, `psycopg2`, and `scikit-fuzzy`) were unavailable in that implementation environment. These are not a full-suite result. Run `python -m pytest -q` in the project's fully provisioned Windows environment before accepting Task 11.

The Task 11 structural audit passed with zero release bundles, zero release-review events, and no active release. This is the expected fail-closed baseline; it does not evidence a clinical approval or active knowledge publication.

## 19.4 Focused Task 09 Verification

| Test category | Result |
|---|---:|
| Food-rule and API focused tests | 55 passed |
| Clinical reasoning tests | 23 passed |
| Full Python suite | 377 passed |
| Frontend production build | Passed |
| npm audit | 0 vulnerabilities |

Focused test counts overlap with the full suite.

## 19.4 Knowledge Structural Validation

The knowledge-validation workflow checks:

- Schema validity.
- Manifest consistency.
- Dataset integrity.
- Evidence references.
- Catalog consistency.
- Governance invariants.
- Release integrity requirements.

Latest reported result:

```text
Structural validation: PASSED
```

Structural validation does not prove clinical correctness.

## 19.5 Task 09 Acceptance Audit

Latest Task 09 audit:

```text
Approved runtime assertions: 0
```

This is an important limitation.

The system must not generate positive clinical findings when no approved assertion exists.

## 19.6 Frontend Verification

From the frontend directory:

```powershell
npm audit

npm run build
```

Latest reported result:

```text
npm audit: 0 vulnerabilities
Production build: PASSED
```

## 19.7 Run All Main Checks

From the repository root:

```powershell
# Python regression suite
python -m pytest -q

# Knowledge structural validation
python -m services.knowledge_validation

# Medication catalog audit
python -m scripts.audit_medication_catalog --output reports\medication_catalog_audit.json

# Knowledge coverage audit
python -m scripts.audit_knowledge_coverage --output reports\knowledge_coverage.json

# Task 07 audit
python -m scripts.audit_task07 --output reports\task07_acceptance_audit.json

# Task 08 audit
python -m scripts.audit_task08 --output reports\task08_acceptance_audit.json

# Task 09 audit
python -m scripts.audit_task09 --output reports\task09_acceptance_audit.json

# Task 10 audit
python -m scripts.audit_task10 --output reports\task10_acceptance_audit.json

# Task 11 release-governance audit
python -m scripts.audit_task11 --output reports\task11_acceptance_audit.json

# Frontend verification
Set-Location frontend

npm audit

npm run build

Set-Location ..
```

The exact command-line arguments for individual scripts should be confirmed with their `--help` output if the local revision differs.

## 19.8 CI/CD

The GitHub Actions workflow is located at:

```text
.github/workflows/tests.yml
```

It runs the automated Python test workflow for configured pushes and pull requests targeting `main`.

CI provides software regression evidence, not clinical validation.

---

# 20. Knowledge Management Workflows

The knowledge-management commands are intended for authorized development and governance operators.

## 20.1 Inspect Evidence Ingestion CLI

```powershell
python -m scripts.ingest_evidence --help
```

## 20.2 Inspect Evidence Review CLI

```powershell
python -m scripts.review_evidence --help
```

## 20.3 Inspect Source Connector CLI

```powershell
python -m scripts.fetch_medical_source --help
```

## 20.4 Inspect Knowledge Management CLI

```powershell
python -m scripts.manage_knowledge --help
```

The exact command syntax is defined by the current script implementations and task documentation.

## 20.5 Governance Lifecycle

```text
External source
      |
      v
Evidence staging
      |
      v
Integrity verification
      |
      v
Evidence inspection
      |
      v
Append-only review decision
      |
      v
Evidence-linked candidate
      |
      v
Independent clinical review
      |
      v
Conflict assessment
      |
      v
Immutable release
      |
      v
Independent clinical-release review
      |
      v
Independent governance-release review
      |
      v
Separate steward/administrator promotion
      |
      v
Runtime verifies manifest, promotion chain,
release-review chain and review digest
```

A schema-valid candidate is not automatically clinically correct.

A promoted software release is not automatically proof of patient-care safety.

---

# 21. Deployment

RxLogic uses a single-service deployment model.

The Flask backend serves the built React frontend from:

```text
frontend/dist/
```

The repository includes:

- `Procfile`.
- `runtime.txt`.
- `requirements.txt`.
- `alembic.ini`.
- `alembic/`.
- `.env.example`.

## 21.1 Hosted Demonstration

Live demonstration:

https://rxlogic-ataf.onrender.com

The existing project deployment target is Render.

## 21.2 Deployment Considerations

For persistent hosting:

- Configure a managed PostgreSQL database.
- Configure secrets through the hosting platform.
- Set `FLASK_DEBUG=false`.
- Build the frontend before deployment.
- Ensure `frontend/dist/` contains current assets.
- Protect knowledge-management and audit artifacts.
- Do not enable active-release mode without a valid approved release.

The hosted demonstration does not provide the local Ollama service used for natural-language parsing.

A successful deployment indicates that the application is running. It does not establish clinical validity.

---

# 22. Security and Privacy

RxLogic uses multiple software-level controls.

## Knowledge Integrity

- SHA-256 source fingerprints.
- Separate source and normalized-payload hashes.
- Evidence metadata integrity.
- Dataset hashes.
- Release manifests.
- Hash-linked promotion events.

## Governance Controls

- Append-only review decisions.
- Evidence-linked candidates.
- Independent clinical-review requirement.
- Conflict assessment.
- Explicit release promotion.
- Dual-control release-level clinical and governance review.
- Separation between release authors, reviewers, and promoter.
- Hash-chained release-review audit log bound to the manifest digest.
- Rationale-bearing, revalidated rollback.
- Fail-closed active-release loading.

## Runtime Controls

- Unreviewed food rules are informational.
- Unapproved clinical assertions are excluded.
- Unresolved conflicts are excluded from findings.
- Missing knowledge is not interpreted as safety.
- Dosage references are not converted into patient-specific instructions.

## Privacy

Use synthetic data only.

Task 09 patient context and context-derived findings are not persisted in plan history.

Do not submit personally identifying information, medical records, or real patient medication regimens.

## Production Governance Limitations

CLI actor IDs and role strings are audit metadata. They are not authenticated identities.

A production governance deployment would still require:

- Strong identity management.
- Authenticated reviewer roles and credential verification.
- Authorization checks enforced by an identity provider.
- Signed release manifests or externally anchored audit records.
- Operational key management.
- Protected audit storage and backups.
- Multi-process/multi-host governance coordination.

---

# 23. Known Limitations

The current project has important limitations.

1. The medication catalog contains only a small development inventory.
2. The knowledge base is not comprehensive.
3. Several legacy interaction assertions remain unreviewed.
4. Several legacy food-guidance entries remain unreviewed.
5. Some medication pairs have not been evaluated.
6. The Task 09 assertion domains currently contain zero approved runtime assertions.
7. No clinical validation study has been performed.
8. No patient-outcome evaluation has been performed.
9. The application does not provide patient-specific dosage calculations.
10. The application does not infer diagnoses.
11. Natural-language parsing requires a local Ollama service.
12. The hosted deployment does not host Ollama.
13. The current CLI governance workflow is not a replacement for authenticated institutional review.
14. No valid active approved knowledge release is configured in the latest reported snapshot.
15. Local Task 11 reviewer IDs and role strings are not authenticated identities or credential verification.
16. Task 11's SHA-256 review chain is tamper-evident, not a digital signature or external trust anchor.
17. Pre-Task-11 releases remain inspectable but must be rebuilt and dual-reviewed before promotion or active runtime loading.
18. The Task 11 full Windows regression run is still pending in the current branch.

These limitations are intentionally documented rather than hidden.

---

# 24. Future Scope

Potential future development directions include:

## Knowledge Expansion

- Expand medication identity coverage.
- Add more source-backed evidence.
- Improve terminology consistency.
- Increase coverage through reviewed and approved knowledge.

## Governance Improvements

- Authenticated reviewer identities.
- Stronger dual-control approval.
- Signed release manifests.
- Improved audit storage.
- Operational key management.

## Reasoning Improvements

- More sophisticated constraint models.
- Improved schedule-explanation traces.
- Expanded evaluation datasets.
- Better parser robustness testing.
- More detailed knowledge-coverage reporting.

## Infrastructure

- Stronger observability.
- Database migration automation.
- Deployment health checks.
- Improved CI integration.
- Performance testing.

## Research and Validation

Any future clinical validation would require a separate, appropriately governed research process, qualified clinical involvement, and applicable regulatory review.

Software development alone does not establish clinical suitability.

---

# 25. Evaluation and Viva Preparation

This section summarizes the project's main technical contributions.

## Q1. What is RxLogic?

RxLogic is a neuro-symbolic medication-reasoning and scheduling demonstrator combining optional LLM-based input parsing with deterministic rule evaluation, fuzzy uncertainty refinement, constraint satisfaction, and goal-stack planning.

It also includes evidence-governed knowledge management and a bounded clinical-assessment API integration.

## Q2. Why use neuro-symbolic architecture?

The neural component provides flexible language interpretation.

The symbolic component provides explicit schemas, inspectable rules, deterministic constraints, and explainable outputs.

Separating these responsibilities reduces dependence on unconstrained LLM-generated decisions.

## Q3. What is the role of the LLM?

The LLM parses natural-language input into candidate structured fields.

It is not the source of clinical truth and does not independently decide interactions or schedule constraints.

## Q4. Why use fuzzy logic?

Fuzzy logic allows graded confidence representations using configured evidence-related inputs rather than relying only on binary classifications.

The resulting values are not clinically calibrated probabilities.

## Q5. Why use CSP scheduling?

Scheduling involves variables, possible assignments, and constraints.

CSP provides a structured way to search for feasible assignments and report infeasible configurations.

## Q6. What is MRV?

Minimum Remaining Values selects the variable with the fewest available values.

It helps prioritize the most constrained variable during search.

## Q7. What is forward checking?

Forward checking removes values that are incompatible with an assignment from neighboring variable domains.

It can identify impossible branches earlier.

## Q8. Why use goal-stack planning?

Goal-stack planning resolves a sequence of goals and provides an inspectable planning trace.

It makes the reasoning process easier to explain than displaying only a final result.

## Q9. Why separate severity and evidence strength?

Severity describes the potential seriousness represented by a rule.

Evidence strength describes how well supported the rule is.

They represent different dimensions.

## Q10. Why is evidence ingestion separate from clinical approval?

Retrieved material may be incomplete, irrelevant, outdated, or incorrectly interpreted.

Separate review and approval stages prevent external source data from silently becoming runtime clinical knowledge.

## Q11. What does SHA-256 accomplish?

It creates a content fingerprint that can be used to detect whether stored content differs from the content originally recorded.

It verifies integrity, not medical truth.

## Q12. What is an immutable knowledge release?

A release is a versioned collection of approved knowledge datasets bound to a manifest of content hashes.

Its creation is separate from explicit activation.

## Q13. What is the purpose of fail-closed loading?

If an active release is missing or fails integrity checks, the runtime refuses to silently use a mutable development knowledge source.

## Q14. What does Task 08 contribute?

Task 08 introduces medication identity catalog management, aliases, RxNorm metadata, and knowledge-coverage auditing.

It includes the paracetamol-to-acetaminophen identity mapping.

## Q15. What does Task 09 contribute?

Task 09 integrates evidence-governed clinical assessment into the plan response.

It evaluates eligible assertions against explicitly supplied context while excluding unapproved and conflicted knowledge.

## Q16. Does RxLogic provide medical advice?

No.

It is an educational and software-engineering demonstrator and is not clinically validated or authorized for patient-care use.

## Q17. What does 377 passed tests mean?

It means the latest reported automated regression suite passed 377 tests in the reported Windows environment.

It does not establish clinical correctness or patient-care safety.

## Q18. What happens when knowledge is missing?

The system reports insufficient or unavailable knowledge.

It must not interpret missing knowledge as evidence that a medication combination is safe.

## Suggested Evaluation Demonstration

A safe demonstration can cover:

1. Application architecture.
2. Structured synthetic input.
3. Medication name normalization.
4. Rule-engine behavior.
5. Knowledge-coverage reporting.
6. CSP scheduling.
7. Goal-stack trace.
8. Task 09 clinical-assessment response.
9. Evidence ingestion and review.
10. Knowledge-release integrity workflow.
11. Automated test results.
12. Known limitations and future scope.

Use synthetic demonstration data only.

---

# 26. Conclusion

RxLogic demonstrates a modular approach to combining neural input interpretation with deterministic symbolic reasoning and evidence-governed knowledge management.

Across Tasks 01–11, the project evolved from an initial medication-reasoning application into a broader software-engineering demonstrator incorporating:

- Full-stack application architecture.
- Optional natural-language parsing.
- Structured domain validation.
- Rule-based reasoning.
- Fuzzy uncertainty representation.
- Constraint-based scheduling.
- Goal-stack planning.
- Medication identity normalization.
- Evidence ingestion and review.
- Knowledge provenance and integrity.
- Independent clinical-review requirements.
- Immutable release management.
- Clinical-assessment integration.
- Automated testing and structural audits.

The latest user-reported pre-Task-11 Windows snapshot passed 384 automated tests. Task 11 adds a focused 46-test release/CLI/clinical-knowledge/audit suite in the implementation environment; the full Task 11 Windows regression run is pending.

The project also explicitly documents the limits of its current knowledge base and the absence of clinical validation.

Its principal contribution is an inspectable engineering architecture that demonstrates how AI-assisted input, symbolic reasoning, constraint solving, and controlled knowledge publication can be separated and integrated within a single application.

---

# 27. License

This project is distributed under the MIT License.

See the [LICENSE](LICENSE) file for the full license text.

---

<p align="center">
  <strong>RxLogic — Explainable Reasoning. Structured Knowledge. Controlled Evidence.</strong>
</p>

<p align="center">
  Built as an educational and software-engineering research demonstrator.
</p>

> **Final Disclaimer:** RxLogic is not a medical device, has not been clinically validated, and is not authorized for patient-care use. Its knowledge base is incomplete. No output should be interpreted as a diagnosis, prescription, dosing instruction, or confirmation of medication safety. Always consult a qualified healthcare professional for real medication decisions.
