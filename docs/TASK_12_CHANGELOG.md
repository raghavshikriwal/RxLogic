# Task 12 Changelog — Security and Deployment Hardening

## Added

- `services/security.py`: validated runtime security configuration, time-bounded HMAC-SHA256 anonymous session-cookie signing/verification, and deployment preflight checks.
- `services/task12_audit.py`: reproducible web-tier security acceptance audit.
- `scripts/audit_task12.py`: JSON-producing Task 12 audit CLI.
- `scripts/security_preflight.py`: deployment configuration preflight.
- `tests/test_security.py`: signing, configuration, and production fail-closed tests.
- `tests/test_app_security.py`: cookie, response-header, error-redaction, and payload-size tests.
- `docs/TASK_12_SECURITY_HARDENING_PROTOCOL.md`: security controls, environment setup, verification, and known limits.
- `.github/workflows/security.yml`: Python dependency audit, Bandit, and frontend dependency audit.
- `requirements-security.txt`: optional static/dependency scanning toolchain.

## Changed

- Signed and timestamped the anonymous history cookie; expired and future-dated tokens are rejected, while the raw UUID remains the database history-scope key.
- Added production-only startup requirements for a strong signing key, persistent PostgreSQL URL, shared Redis rate-limit store, and disabled debug mode.
- Added optional, explicitly configured `ProxyFix` trusted-proxy handling.
- Added 64 KiB request limit, strict medication input bounds, natural-language length bound, and revalidation of LLM-extracted medications.
- Redacted raw request bodies from schema-validation messages.
- Added security headers, HTML CSP, API no-store headers, production HSTS, and generic API exception responses.
- Made rate-limit storage configurable through each Flask app configuration; the validated Redis/memory URI is passed to Flask-Limiter at app initialization rather than being frozen at module import.
- Enabled the Flask-Limiter Redis extra so the configured production Redis backend is installable.
- Changed the deployment Procfile to enforce production mode, run the security preflight, and bind Gunicorn to the platform `PORT` before accepting traffic.
- Updated Flask to 3.1.3, Gunicorn to 26.2.0, Requests to 2.34.2, python-dotenv to 1.2.4, SQLAlchemy to 2.0.57, and psycopg2-binary to 2.9.13; retained SQLAlchemy 2.0 rather than making an unreviewed 2.1 migration.
- Updated CI to run the Task 12 acceptance audit.
- Expanded secret/runtime-artifact ignore patterns and `.env.example` deployment settings.

## Explicit non-goals / limitations

- No public governance/admin HTTP API was added.
- Reviewer identity, professional credentials, MFA, and authorization are not provided by CLI actor/role strings.
- The signed history cookie is not user authentication.
- This task does not establish penetration-test coverage, regulatory compliance, clinical validation, or patient-care authorization.
