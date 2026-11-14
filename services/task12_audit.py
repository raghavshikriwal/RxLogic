"""Reproducible software-security acceptance audit for Task 12.

This audit checks application controls and their configuration. It is not a
penetration test, identity-provider assessment, HIPAA assessment, or clinical
safety certification.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from services.security import build_security_settings, sign_session_id, verify_session_cookie


def run_task12_audit(app: Any | None = None) -> dict[str, Any]:
    if app is None:
        from app import create_app
        app = create_app()

    signing_key = app.config["RXLOGIC_SESSION_SIGNING_KEY"]
    sample_id = "7f9e2f3b-4dd8-4b2f-9c75-7a6b45a8d0e1"
    signed_cookie = sign_session_id(sample_id, signing_key)
    tampered_cookie = signed_cookie[:-1] + ("0" if signed_cookie[-1] != "0" else "1")

    with app.test_client() as client:
        health_response = client.get("/api/health")
        plans_response = client.get("/api/plans")
        knowledge_response = client.get("/api/knowledge/status")
        oversized_response = client.post(
            "/api/plan",
            data=b" " * (65536 + 1),
            content_type="application/json",
        )
        headers = health_response.headers
        cookie_header = plans_response.headers.get("Set-Cookie", "")
        knowledge_payload = knowledge_response.get_json(silent=True) or {}

    route_paths = {rule.rule for rule in app.url_map.iter_rules()}
    environment = app.config["RXLOGIC_ENV"]
    checks = {
        "signed_session_cookie_round_trip": verify_session_cookie(signed_cookie, signing_key) == sample_id,
        "tampered_session_cookie_rejected": verify_session_cookie(tampered_cookie, signing_key) is None,
        "expired_session_cookie_rejected": verify_session_cookie(
            sign_session_id(sample_id, signing_key, issued_at=1), signing_key
        ) is None,
        "session_cookie_is_http_only": "HttpOnly" in cookie_header,
        "session_cookie_has_same_site_policy": "SameSite=Lax" in cookie_header,
        "session_cookie_has_90_day_max_age": "Max-Age=7776000" in cookie_header,
        "session_cookie_secure_in_production": environment != "production" or "Secure" in cookie_header,
        "api_cache_is_disabled": "no-store" in health_response.headers.get("Cache-Control", ""),
        "nosniff_header_present": headers.get("X-Content-Type-Options") == "nosniff",
        "frame_protection_present": headers.get("X-Frame-Options") == "DENY",
        "referrer_policy_present": headers.get("Referrer-Policy") == "strict-origin-when-cross-origin",
        "permissions_policy_present": bool(headers.get("Permissions-Policy")),
        "request_size_limit_configured": app.config.get("MAX_CONTENT_LENGTH") == 65536,
        "oversized_json_request_rejected": oversized_response.status_code == 413 and oversized_response.is_json,
        "production_secret_guard_enforced": _production_secret_guard_enforced(),
        "production_debug_guard_enforced": _production_debug_guard_enforced(),
        "production_persistent_database_guard_enforced": _production_database_guard_enforced(),
        "production_shared_rate_limit_guard_enforced": _production_rate_limit_guard_enforced(),
        "trusted_proxy_handling_is_explicit": (
            (app.config["RXLOGIC_TRUSTED_PROXY_HOPS"] == 0 and app.wsgi_app.__class__.__name__ != "ProxyFix")
            or (app.config["RXLOGIC_TRUSTED_PROXY_HOPS"] > 0 and app.wsgi_app.__class__.__name__ == "ProxyFix")
        ),
        "governance_admin_api_not_exposed": not any(
            path.startswith(("/api/admin", "/api/governance")) for path in route_paths
        ),
        "clinical_use_remains_unavailable": (
            knowledge_payload.get("clinical_use_permitted") is False
            or knowledge_response.status_code >= 500
        ),
        "production_hsts_enabled": environment != "production" or headers.get("Strict-Transport-Security") == "max-age=31536000",
        "rate_limit_backend_matches_validated_config": (
            app.config.get("RATELIMIT_STORAGE_URI") == app.config.get("RXLOGIC_RATE_LIMIT_STORAGE_URI")
        ),
        "deployment_procfile_runs_production_preflight": _procfile_enforces_production_preflight(),
    }

    warnings: list[str] = [
        "This is an application-control audit, not a penetration test or external security certification.",
        "The time-bounded anonymous signed cookie scopes browser history; it does not authenticate a user or prevent replay of a stolen token during its validity window.",
        "Task 11 governance CLI reviewer IDs and role declarations are not authenticated identities or verified professional credentials.",
        "No public governance/admin HTTP API is exposed. Administrative operations remain local CLI operations and depend on host/shell access controls.",
        "A successful software security audit does not authorize clinical use.",
    ]
    if app.config["RXLOGIC_RATE_LIMIT_STORAGE_URI"].startswith("memory://"):
        warnings.append("Rate limiting uses process-local memory; configure managed Redis before multi-worker or multi-instance production deployment.")
    if app.config["RXLOGIC_TRUSTED_PROXY_HOPS"] == 0:
        warnings.append("Trusted proxy count is zero; configure the exact reverse-proxy hop count if the host sits behind a proxy and IP-based limits must use the real client IP.")

    return {
        "schema_version": "1.0.0",
        "audit_type": "task12_web_application_security_hardening_audit",
        "passed": all(checks.values()),
        "checks": checks,
        "runtime": {
            "environment": environment,
            "max_request_bytes": app.config.get("MAX_CONTENT_LENGTH"),
            "rate_limit_storage": _storage_class(app.config["RXLOGIC_RATE_LIMIT_STORAGE_URI"]),
            "trusted_proxy_hops": app.config["RXLOGIC_TRUSTED_PROXY_HOPS"],
            "governance_admin_http_routes": sorted(
                path for path in route_paths if path.startswith(("/api/admin", "/api/governance"))
            ),
            "clinical_use_permitted": False,
        },
        "warnings": warnings,
        "limitations": [
            "The audit does not verify external Redis availability, firewall rules, TLS termination, host hardening, database backups, or secrets-manager access controls.",
            "Reviewer authentication and professional credential verification require an identity provider and are not implemented by the local CLI actor fields.",
            "The time-bounded signed anonymous history cookie is a bearer token for history scoping, not a user login and not a substitute for account authentication.",
            "The audit does not establish regulatory compliance, clinical correctness, or patient-care readiness.",
        ],
    }


def _storage_class(uri: str) -> str:
    lowered = uri.lower()
    if lowered.startswith("rediss://"):
        return "redis_tls"
    if lowered.startswith("redis://"):
        return "redis"
    if lowered.startswith("memory://"):
        return "process_local_memory"
    return "other_configured_backend"


def _production_secret_guard_enforced() -> bool:
    try:
        build_security_settings({
            "RXLOGIC_ENV": "production",
            "FLASK_DEBUG": "false",
            "RXLOGIC_SESSION_SIGNING_KEY": "",
            "DATABASE_URL": "postgresql://user:password@host/database",
            "RXLOGIC_RATE_LIMIT_STORAGE_URI": "rediss://redis.example.invalid:6379/0",
        })
    except ValueError as exc:
        return "RXLOGIC_SESSION_SIGNING_KEY" in str(exc)
    return False


def _production_debug_guard_enforced() -> bool:
    try:
        build_security_settings({
            "RXLOGIC_ENV": "production",
            "FLASK_DEBUG": "true",
            "RXLOGIC_SESSION_SIGNING_KEY": "x" * 48,
            "DATABASE_URL": "postgresql://user:password@host/database",
            "RXLOGIC_RATE_LIMIT_STORAGE_URI": "rediss://redis.example.invalid:6379/0",
        })
    except ValueError as exc:
        return "FLASK_DEBUG" in str(exc)
    return False


def _production_database_guard_enforced() -> bool:
    try:
        build_security_settings({
            "RXLOGIC_ENV": "production",
            "FLASK_DEBUG": "false",
            "RXLOGIC_SESSION_SIGNING_KEY": "x" * 48,
            "DATABASE_URL": "sqlite:///:memory:",
            "RXLOGIC_RATE_LIMIT_STORAGE_URI": "rediss://redis.example.invalid:6379/0",
        })
    except ValueError as exc:
        return "PostgreSQL DATABASE_URL" in str(exc)
    return False


def _production_rate_limit_guard_enforced() -> bool:
    try:
        build_security_settings({
            "RXLOGIC_ENV": "production",
            "FLASK_DEBUG": "false",
            "RXLOGIC_SESSION_SIGNING_KEY": "x" * 48,
            "DATABASE_URL": "postgresql://user:password@host/database",
            "RXLOGIC_RATE_LIMIT_STORAGE_URI": "memory://",
        })
    except ValueError as exc:
        return "Redis" in str(exc)
    return False


def _procfile_enforces_production_preflight() -> bool:
    """Ensure the hosted web command gates startup before launching Gunicorn."""
    procfile = Path(__file__).resolve().parents[1] / "Procfile"
    try:
        command = procfile.read_text(encoding="utf-8")
    except OSError:
        return False
    normalized = " ".join(command.split())
    return (
        "export RXLOGIC_ENV=production" in normalized
        and "python -m scripts.security_preflight" in normalized
        and "gunicorn" in normalized
        and "app:app" in normalized
    )
