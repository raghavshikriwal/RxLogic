# Task 12 — Security and Deployment Hardening Protocol

## 1. Purpose

Task 12 hardens the existing Flask/React research demonstrator. It does not add a public administration API, create user accounts, or certify the service for clinical use.

## 2. Implemented application controls

### 2.1 Anonymous history cookie integrity

- The `rxlogic_sid` cookie now contains a canonical UUID, issue timestamp, and HMAC-SHA256 signature.
- The raw UUID remains the database `session_id`; the signature is verified before the cookie is trusted.
- Invalid, unsigned, altered, or non-canonical values are discarded and replaced with a new server-generated UUID.
- The cookie is `HttpOnly`, `SameSite=Lax`, path `/`, and limited to 90 days by both browser `Max-Age` and server-side timestamp verification. Expired or materially future-dated tokens are rejected.
- Production cookies are `Secure` and production startup requires `RXLOGIC_SESSION_SIGNING_KEY` with at least 32 bytes.
- This cookie is a bearer token for anonymous history scoping. It is not login, identity proof, or a reviewer credential.

### 2.2 Request limits and schema validation

- Flask request bodies are limited to 64 KiB.
- Structured and parsed medication batches are limited to 25 entries.
- Medication names are limited to 120 characters.
- Natural-language input is limited to 4,000 characters before the local parser is called.
- Dosage syntax must be a finite positive numeric value no greater than 100,000 mg; this is a defensive input bound, not a recommended-dose range or clinical rule.
- Frequency must be an integer from 1 through 6, matching the existing frontend control; booleans are rejected as integers.
- `with_food` must be a boolean or null.
- Unknown request and medication fields are rejected.
- LLM-extracted objects are revalidated against the same API boundary before entering the reasoning pipeline.
- Validation errors redact the raw request body rather than echoing potentially sensitive medication/context data.

### 2.3 HTTP response hardening

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy` disables camera, microphone, and geolocation.
- Cross-origin opener/resource policies are same-origin.
- API responses use `Cache-Control: no-store` and `Pragma: no-cache`.
- HTML receives a Content Security Policy compatible with the locally served React bundle and the Google Fonts assets referenced by the current frontend.
- Production responses receive HSTS.
- Unhandled API exceptions are logged server-side and return a generic error message without exception details.

### 2.4 Production configuration

Set the following variables in the hosting platform's secret/configuration manager:

| Variable | Production requirement |
|---|---|
| `RXLOGIC_ENV` | `production` |
| `RXLOGIC_SESSION_SIGNING_KEY` | Unique random secret, at least 32 bytes |
| `FLASK_DEBUG` | `false` |
| `DATABASE_URL` | Persistent PostgreSQL connection; SQLite is rejected in production |
| `RXLOGIC_RATE_LIMIT_STORAGE_URI` | Managed Redis URL (`redis://` or `rediss://`) |
| `RXLOGIC_TRUSTED_PROXY_HOPS` | Exact number of trusted reverse proxies, if applicable |

Generate a signing key with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not paste that value into source control, issue trackers, or chat. Configure it only in the deployment secret manager.

Run the production preflight before deployment:

```powershell
python -m scripts.security_preflight
```

The app itself refuses to start in production without a strong session signing key, a persistent PostgreSQL `DATABASE_URL`, a Redis rate-limit backend, and debug mode disabled.

The repository `Procfile` explicitly sets `RXLOGIC_ENV=production`, runs the preflight, and only then starts Gunicorn bound to `0.0.0.0:${PORT:-8000}`. The hosting platform must provide the required database, signing-key, and Redis settings; placeholder values from `.env.example` are rejected.

### 2.5 Reverse proxies and rate limits

`ProxyFix` is disabled unless `RXLOGIC_TRUSTED_PROXY_HOPS` is explicitly set. Configure only the actual trusted proxy count. An incorrect value can let untrusted forwarded headers influence client-address handling.

Flask-Limiter retains the route-level limits already present (`/api/plan`, `/api/plan/nl`, and `/api/plans`). The `Flask-Limiter[redis]` dependency installs Redis backend support. `memory://` is process-local and suitable only for local development/tests or a single-process demonstration. Production requires shared Redis storage so Gunicorn workers and instances use the same counters.

The Task 12 dependency baseline updates Flask to 3.1.3, Gunicorn to 26.2.0, Requests to 2.34.2, python-dotenv to 1.2.4, SQLAlchemy to 2.0.57, and psycopg2-binary to 2.9.13. Flask 3.1.3 includes the upstream fix for GHSA-68rp-wp8r-4726; Requests 2.34.2 is newer than the fixes for CVE-2024-47081 and CVE-2026-25645. Gunicorn is moved from the unsupported 22.0.0 line to the maintained 26.x release line. SQLAlchemy stays on the 2.0 maintenance series to avoid an unreviewed major/minor ORM migration. The dependency scan remains authoritative for the full resolved environment.

### 2.6 Governance and identity boundary

Task 11 knowledge-management mutations remain local CLI operations. No `/api/admin` or `/api/governance` endpoint is exposed. The CLI's `--reviewer-id`, `--actor-id`, and role fields remain audit declarations and are not proof of authenticated identity or professional credentials.

Do not expose shell access to the deployment host to untrusted users. A real reviewer/admin authentication system requires a separately selected identity provider, account lifecycle, credential verification, MFA policy, role assignment, and auditable authorization integration. Task 12 does not fake those functions with a shared token or user-supplied role string.

## 3. Security verification

Run:

```powershell
python -m pytest tests\test_security.py tests\test_app_security.py -q
python -m scripts.audit_task12 --output reports\task12_acceptance_audit.json
python -m scripts.security_preflight
python -m pytest -q
```

Static/dependency checks are defined in `.github/workflows/security.yml`:

- `pip-audit` checks Python dependency advisories.
- Bandit scans the Python application and service code.
- `npm audit --audit-level=high` checks frontend dependencies.

A scanner result is only as current as its vulnerability database and dependency lock state; review and update dependencies rather than suppressing findings without rationale.

## 4. Acceptance criteria

- Production configuration refuses missing/weak signing keys, debug mode, SQLite databases, and process-local rate-limit storage.
- Anonymous history cookies are signed, time-bounded, and tampering/expiry are rejected.
- Cookie attributes and browser security headers are tested.
- API inputs are size-bounded and schema-validated before reasoning/LLM work.
- Raw request bodies are not included in schema-validation messages.
- API exceptions do not disclose stack traces or secrets to clients.
- Security and dependency checks run in CI.
- Governance remains local CLI-only; identity authentication is explicitly marked as a deployment dependency.
- Clinical use remains prohibited unless separately validated and authorized.

## 5. Limitations

This protocol and its tests do not constitute a penetration test, threat-model sign-off, privacy-law assessment, HIPAA assessment, formal security certification, clinical validation, or authorization for patient care. They do not verify that external Redis, TLS, hosting firewalls, secret-manager permissions, backups, or host operating-system controls are correctly configured. Those must be verified in the target deployment environment.
