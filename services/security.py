"""Security configuration and cryptographic helpers for the RxLogic web tier.

The anonymous history cookie is a signed, opaque session-scope token. It is
not an authentication credential and must never be treated as proof of a
person's identity or clinical role.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import uuid
from typing import Mapping
from urllib.parse import urlsplit


MAX_REQUEST_BYTES = 64 * 1024
MIN_PRODUCTION_KEY_BYTES = 32
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 90
SESSION_COOKIE_CLOCK_SKEW_SECONDS = 60
VALID_ENVIRONMENTS = {"development", "test", "production"}
POSTGRES_SCHEMES = {"postgresql", "postgres", "postgresql+psycopg2"}
REDIS_SCHEMES = {"redis", "rediss"}


def _has_valid_service_endpoint(value: str, schemes: set[str], *, require_path: bool) -> bool:
    if not value or any(marker in value for marker in "<>\r\n\t "):
        return False
    try:
        parsed = urlsplit(value)
        # Accessing .port validates any explicit port. If omitted, the
        # client library uses its protocol default.
        _ = parsed.port
        return (
            parsed.scheme.lower() in schemes
            and bool(parsed.hostname)
            and (not require_path or bool(parsed.path.strip("/")))
        )
    except ValueError:
        return False


def _env_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("boolean environment setting must be true/false, 1/0, yes/no, or on/off")


def build_security_settings(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    """Build validated settings without mutating the process environment.

    Production deliberately fails startup when no sufficiently strong
    session signing key is configured or Flask debug mode is enabled.
    Development/test may use an ephemeral process-local signing key.
    """
    source = os.environ if environ is None else environ
    environment = source.get("RXLOGIC_ENV", "development").strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError("RXLOGIC_ENV must be development, test, or production")

    debug_enabled = _env_bool(source.get("FLASK_DEBUG"), default=False)
    if environment == "production" and debug_enabled:
        raise ValueError("FLASK_DEBUG must be false when RXLOGIC_ENV=production")

    supplied_key = source.get("RXLOGIC_SESSION_SIGNING_KEY", "")
    if supplied_key and supplied_key.strip():
        signing_key = supplied_key.encode("utf-8")
        if len(signing_key) < MIN_PRODUCTION_KEY_BYTES:
            raise ValueError("RXLOGIC_SESSION_SIGNING_KEY must contain at least 32 bytes")
    elif environment == "production":
        raise ValueError("RXLOGIC_SESSION_SIGNING_KEY is required in production and must be at least 32 bytes")
    else:
        signing_key = secrets.token_bytes(MIN_PRODUCTION_KEY_BYTES)

    proxy_hops_raw = source.get("RXLOGIC_TRUSTED_PROXY_HOPS", "0")
    try:
        proxy_hops = int(proxy_hops_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("RXLOGIC_TRUSTED_PROXY_HOPS must be an integer from 0 to 10") from exc
    if not 0 <= proxy_hops <= 10:
        raise ValueError("RXLOGIC_TRUSTED_PROXY_HOPS must be an integer from 0 to 10")

    rate_limit_storage_uri = source.get("RXLOGIC_RATE_LIMIT_STORAGE_URI", "memory://").strip()
    if not rate_limit_storage_uri:
        raise ValueError("RXLOGIC_RATE_LIMIT_STORAGE_URI cannot be empty")

    if environment == "production":
        database_url = source.get("DATABASE_URL", "").strip().lower()
        if not _has_valid_service_endpoint(database_url, POSTGRES_SCHEMES, require_path=True):
            raise ValueError("Production requires a persistent PostgreSQL DATABASE_URL; SQLite is not suitable")
        if not _has_valid_service_endpoint(rate_limit_storage_uri, REDIS_SCHEMES, require_path=False):
            raise ValueError("Production requires Redis via RXLOGIC_RATE_LIMIT_STORAGE_URI for shared rate limiting")

    return {
        "environment": environment,
        "debug": debug_enabled if environment != "production" else False,
        "session_signing_key": signing_key,
        "session_cookie_secure": environment == "production",
        "session_cookie_httponly": True,
        "session_cookie_samesite": "Lax",
        "session_cookie_path": "/",
        "max_content_length": MAX_REQUEST_BYTES,
        "trusted_proxy_hops": proxy_hops,
        "rate_limit_storage_uri": rate_limit_storage_uri,
        "hsts_enabled": environment == "production",
    }


def sign_session_id(session_id: str, signing_key: bytes, *, issued_at: int | None = None) -> str:
    """Return a time-bounded signed token; only the raw UUID is stored in PlanLog."""
    try:
        canonical_id = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("session_id must be a UUID") from exc
    if canonical_id != session_id:
        raise ValueError("session_id must be a canonical UUID")
    issued_at = int(time.time()) if issued_at is None else issued_at
    if isinstance(issued_at, bool) or not isinstance(issued_at, int) or issued_at < 0:
        raise ValueError("issued_at must be a non-negative integer timestamp")
    message = f"{canonical_id}.{issued_at}".encode("ascii")
    signature = hmac.new(signing_key, message, hashlib.sha256).hexdigest()
    return f"{canonical_id}.{issued_at}.{signature}"


def verify_session_cookie(
    value: str,
    signing_key: bytes,
    *,
    max_age_seconds: int = SESSION_COOKIE_MAX_AGE_SECONDS,
    now: int | None = None,
) -> str | None:
    """Verify signature and age, returning the UUID only for a current token."""
    if not isinstance(value, str) or len(value) > 128 or value.count(".") != 2:
        return None
    session_id, issued_at_raw, supplied_signature = value.split(".", 2)
    try:
        canonical_id = str(uuid.UUID(session_id))
    except (ValueError, TypeError, AttributeError):
        return None
    if canonical_id != session_id or not issued_at_raw.isascii() or not issued_at_raw.isdigit() or len(supplied_signature) != 64:
        return None
    issued_at = int(issued_at_raw)
    if str(issued_at) != issued_at_raw:
        return None
    current_time = int(time.time()) if now is None else now
    if isinstance(current_time, bool) or not isinstance(current_time, int):
        return None
    if isinstance(max_age_seconds, bool) or not isinstance(max_age_seconds, int) or max_age_seconds <= 0:
        return None
    age = current_time - issued_at
    if age < -SESSION_COOKIE_CLOCK_SKEW_SECONDS or age > max_age_seconds:
        return None
    message = f"{canonical_id}.{issued_at}".encode("ascii")
    expected = hmac.new(signing_key, message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_signature):
        return None
    return canonical_id


def security_preflight(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    """Return deployment checks; warnings are not silently promoted to passes."""
    source = os.environ if environ is None else environ
    problems: list[str] = []
    warnings: list[str] = []
    environment = source.get("RXLOGIC_ENV", "development").strip().lower()

    try:
        settings = build_security_settings(source)
    except ValueError as exc:
        return {
            "passed": False,
            "environment": environment,
            "checks": {},
            "errors": [str(exc)],
            "warnings": warnings,
        }

    checks: dict[str, bool] = {
        "environment_valid": environment in VALID_ENVIRONMENTS,
        "debug_disabled_in_production": environment != "production" or not bool(settings["debug"]),
        "session_signing_key_configured": bool(source.get("RXLOGIC_SESSION_SIGNING_KEY")) if environment == "production" else True,
        "request_size_limit_configured": settings["max_content_length"] == MAX_REQUEST_BYTES,
    }

    if environment == "production":
        database_url = source.get("DATABASE_URL", "").strip().lower()
        checks["persistent_database_configured"] = _has_valid_service_endpoint(
            database_url, POSTGRES_SCHEMES, require_path=True
        )
        if not checks["persistent_database_configured"]:
            problems.append("Production requires a persistent PostgreSQL DATABASE_URL; SQLite is not suitable.")

        rate_uri = str(settings["rate_limit_storage_uri"]).lower()
        checks["shared_rate_limit_storage_configured"] = _has_valid_service_endpoint(
            rate_uri, REDIS_SCHEMES, require_path=False
        )
        if not checks["shared_rate_limit_storage_configured"]:
            problems.append("Production requires a shared Redis rate-limit store via RXLOGIC_RATE_LIMIT_STORAGE_URI.")

        if int(settings["trusted_proxy_hops"]) == 0:
            warnings.append("No trusted proxy hops configured; verify client IP behavior behind the hosting proxy.")
    else:
        if str(settings["rate_limit_storage_uri"]).startswith("memory://"):
            warnings.append("In-memory rate limiting is process-local and is intended only for development/tests or a single-process demonstration.")

    return {
        "passed": not problems and all(checks.values()),
        "environment": environment,
        "checks": checks,
        "errors": problems,
        "warnings": warnings,
    }
