# Task 12 Acceptance Audit

Run the reproducible audit from the repository root:

```powershell
python -m scripts.audit_task12 --output reports\task12_acceptance_audit.json
```

The generated JSON report is the authoritative record for the environment in which the audit ran. It checks cookie signing/tamper rejection, cookie attributes, response headers, API cache controls, request limits, production secret/debug guards, and the absence of network-facing governance/admin routes.

The report also records environment-dependent warnings for process-local rate-limit storage and proxy configuration. Passing the software audit does not verify that managed Redis, TLS termination, deployment secrets, host controls, or an identity provider are correctly configured.

Clinical use remains disabled and is not authorized by this audit.
