# Task 13 Changelog — Label-Cited Interaction Rule Expansion

Release: `rxlogic-task13-development-2026-11-14` (still `development_unreviewed`; clinical use not permitted).

## Added
- 28 drug-drug interaction rules (12 → 40) in `knowledge/interaction_rules.json`, each citing 1–3 sources (`SRC-CITED-*`).
- 14 evidence sources in `knowledge/evidence_sources.json`: FDA labels (Drugs@FDA), DailyMed SPLs, one MHRA notice, one Health Canada monograph, one journal table. Each has publisher, title, version, locator, HTTPS URL, jurisdiction and retrieval date.
- 13 medications (11 → 24): simvastatin, amlodipine, clopidogrel, calcium carbonate, methotrexate, sildenafil, nitroglycerin, digoxin, amiodarone, tramadol, alprazolam, sertraline, clarithromycin — with brand/Indian-brand aliases.
- `services/rxcui_verification.py` and `scripts/verify_rxcuis.py`: cross-check every catalog RxCUI against RxNav (identity only).
- `tests/test_task13_rule_expansion.py`, `tests/test_rxcui_verification.py`.

## Changed
- `services/medication_catalog.py`: status vocabularies are named constants; added `added_task13_rule_expansion` and `cited_assertions_unreviewed_partial`.
- `Xanax` is now an alias of alprazolam, so unknown-drug test fixtures use `Trazodone`.
- Coverage/catalog/task08 test counts updated (24 medications, 276 pairs, 40 assertions present, 236 not evaluated).
- Regenerated `reports/` audit outputs affected by the new release.

## Limits (read before relying on this)
- Citations were located and section headings/excerpts confirmed by web search on 2026-11-14; the full documents were **not** independently re-read, and **no pharmacist/physician review has happened**. Every rule stays `needs_clinical_review`; every source is `citation_recorded_pending_review`.
- RxCUIs for the 13 new medications must be confirmed with `python -m scripts.verify_rxcuis` (needs network).
- Severity/evidence grades are the author's reading of label language, not a published grading scheme.
- No food-rule, contraindication or dosage knowledge was added for the new medications.
