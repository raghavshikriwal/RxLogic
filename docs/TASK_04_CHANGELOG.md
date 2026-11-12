# Task 04 — Official medical-source connectors

## Added

- `services/medical_source_client.py` provides bounded fetch-and-stage adapters for RxNav/RxNorm, openFDA drug labels, and DailyMed SPL search.
- `scripts/fetch_medical_source.py` provides an operator CLI for live source retrieval.
- Added `rxnorm_concept` and `dailymed_spl` evidence source types to the Task 03 staging validator.
- `tests/test_medical_source_client.py` covers request construction, staging metadata, failures, response limits, and runtime knowledge isolation.
- `docs/TASK_04_SOURCE_CONNECTORS.md` documents use, limitations, and official API references.

## Safety controls

- Fixed HTTPS provider endpoints; no caller-supplied URLs.
- Redirects disabled, finite timeout, maximum response size, bounded result limits.
- All fetched payloads flow through the existing evidence staging service.
- No runtime knowledge promotion or rule generation.
- No clinical conclusions are inferred from API responses.

## Validation

Automated tests use mocked HTTP responses and do not require live external network access. Passing tests verify connector and staging behavior, not clinical validity or provider uptime.
