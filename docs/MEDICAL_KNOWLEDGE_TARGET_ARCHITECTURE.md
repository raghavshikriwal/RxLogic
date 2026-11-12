# RxLogic Medical Knowledge Target Architecture

This document is a concise architecture reference for future implementation. It does not represent implemented functionality.

## Design principles

1. **Source-first:** Every clinical assertion must be traceable to a source locator.
2. **No silent inference:** Missing or conflicting data stays missing or conflicting; it is never treated as safe.
3. **Stable identity:** Concepts and assertions use stable IDs, not array positions or display names.
4. **Separate concepts:** Drug ingredient, clinical drug, branded product, formulation, route and package are not interchangeable.
5. **Separate evidence dimensions:** Clinical severity, evidence certainty, source quality, applicability and algorithmic confidence remain distinct.
6. **Immutable releases:** Ingestion creates candidate data; only validated and reviewed snapshots are published to runtime.
7. **Reproducibility:** Every runtime result identifies the knowledge release and source records used.
8. **Privacy by design:** Patient context is minimized, optional, purpose-limited and not stored by default without an explicit product requirement.
9. **LLM containment:** An LLM may help extract or summarize; it cannot create or approve clinical facts.
10. **Human clinical governance:** Clinical claims and intended use require qualified review before any clinical deployment.

## Suggested logical entities

| Entity | Responsibility |
|---|---|
| `Substance` | Active ingredient or chemical substance concept |
| `DrugProduct` | Ingredient combination, strength, dose form, route and release characteristics |
| `Brand` | Brand/trade name and its mapping to a product |
| `TerminologyMapping` | External identifiers and mapping provenance |
| `ClinicalCondition` | Disease, disorder or clinical condition concept |
| `ClinicalAssertion` | Typed claim such as interaction, contraindication, adverse effect or monitoring requirement |
| `EvidenceSource` | Publisher, document, version, locator, dates and rights metadata |
| `AssertionEvidence` | Links a claim to one or more supporting/contradicting evidence sources |
| `ReviewRecord` | Reviewer role, review outcome, date and rationale |
| `KnowledgeRelease` | Immutable approved dataset version and manifest |
| `PatientContext` | Optional, separately governed context used only where intended and validated |

## Assertion types to model separately

- Drug-drug interaction
- Drug-food interaction
- Drug-supplement interaction
- Contraindication
- Precaution
- Adverse effect
- Dose reference
- Administration instruction
- Laboratory monitoring requirement
- Condition-treatment guideline

Each type needs its own required fields and validation rules. Do not force every claim into a generic pairwise interaction record.

## Ingestion and publication lifecycle

`DISCOVERED -> FETCHED -> NORMALIZED -> VALIDATED -> NEEDS_REVIEW -> REVIEWED -> RELEASED`

Possible terminal or side states include `REJECTED`, `WITHDRAWN`, `SUPERSEDED`, and `CONFLICTING`. Only records in an approved release should be available to the production reasoning service. Preserve original payloads and hashes where source terms permit. Never overwrite raw source material with normalized data.

## Runtime response requirements

A future knowledge-backed response should include:

- Knowledge release identifier.
- Domain coverage and explicit unknown/not-evaluated states.
- Assertion IDs and source locators.
- Evidence/review status.
- Applicability limits and relevant missing patient context.
- Clear educational scope and escalation language for serious warnings.

An absence of a matching assertion must not be serialized as "no interaction" or "safe" unless a separately governed and explicitly defined assessment supports that exact conclusion.

## Candidate source families

Use provider-specific adapters and check terms, licensing and permitted redistribution before ingestion:

- NLM RxNorm/RxNav for medication terminology and concept identifiers.
- DailyMed and FDA/openFDA for US regulatory label content and safety data.
- WHO classifications and essential-medicine resources for international terminology/context.
- ICMR and CDSCO publications for India-specific clinical/regulatory context.
- NICE and other recognized guideline publishers for guideline content.
- Peer-reviewed literature repositories for supporting and conflicting evidence.

These sources have different purposes and jurisdictions. They are not interchangeable, and an API result is not automatically a clinically reviewed assertion.
