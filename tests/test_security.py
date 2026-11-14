from __future__ import annotations

import pytest

from services.security import build_security_settings, sign_session_id, verify_session_cookie


PRODUCTION_ENV = {
    "RXLOGIC_ENV": "production",
    "FLASK_DEBUG": "false",
    "RXLOGIC_SESSION_SIGNING_KEY": "s" * 48,
    "DATABASE_URL": "postgresql://user:secret@db.example.invalid/rxlogic",
    "RXLOGIC_RATE_LIMIT_STORAGE_URI": "rediss://:secret@redis.example.invalid:6379/0",
}


def test_development_settings_use_ephemeral_signing_key_and_bounded_request_size():
    settings = build_security_settings({"RXLOGIC_ENV": "development"})
    assert isinstance(settings["session_signing_key"], bytes)
    assert len(settings["session_signing_key"]) >= 32
    assert settings["session_cookie_secure"] is False
    assert settings["max_content_length"] == 65536


def test_production_settings_require_strong_session_key_and_use_secure_cookie():
    settings = build_security_settings(PRODUCTION_ENV)
    assert settings["session_cookie_secure"] is True
    assert settings["session_cookie_httponly"] is True
    assert settings["session_cookie_samesite"] == "Lax"
    assert settings["hsts_enabled"] is True


def test_production_rejects_missing_signing_key():
    env = {**PRODUCTION_ENV, "RXLOGIC_SESSION_SIGNING_KEY": ""}
    with pytest.raises(ValueError, match="RXLOGIC_SESSION_SIGNING_KEY"):
        build_security_settings(env)


def test_production_rejects_weak_signing_key():
    env = {**PRODUCTION_ENV, "RXLOGIC_SESSION_SIGNING_KEY": "short"}
    with pytest.raises(ValueError, match="at least 32 bytes"):
        build_security_settings(env)


def test_production_rejects_debug_mode():
    env = {**PRODUCTION_ENV, "FLASK_DEBUG": "true"}
    with pytest.raises(ValueError, match="FLASK_DEBUG"):
        build_security_settings(env)


def test_production_requires_persistent_database():
    env = {**PRODUCTION_ENV, "DATABASE_URL": "sqlite:///:memory:"}
    with pytest.raises(ValueError, match="PostgreSQL DATABASE_URL"):
        build_security_settings(env)


def test_production_rejects_file_backed_sqlite_as_single_host_storage():
    env = {**PRODUCTION_ENV, "DATABASE_URL": "sqlite:///rxlogic.db"}
    with pytest.raises(ValueError, match="PostgreSQL DATABASE_URL"):
        build_security_settings(env)


def test_production_rejects_malformed_database_and_redis_endpoints():
    with pytest.raises(ValueError, match="PostgreSQL DATABASE_URL"):
        build_security_settings({**PRODUCTION_ENV, "DATABASE_URL": "postgresql://"})
    with pytest.raises(ValueError, match="PostgreSQL DATABASE_URL"):
        build_security_settings({**PRODUCTION_ENV, "DATABASE_URL": "postgresql://<user>:<password>@<host>/<dbname>"})
    with pytest.raises(ValueError, match="Redis"):
        build_security_settings({**PRODUCTION_ENV, "RXLOGIC_RATE_LIMIT_STORAGE_URI": "rediss://"})
    with pytest.raises(ValueError, match="Redis"):
        build_security_settings({**PRODUCTION_ENV, "RXLOGIC_RATE_LIMIT_STORAGE_URI": "rediss://:<password>@<host>:6379/0"})


def test_production_requires_shared_redis_rate_limit_store():
    env = {**PRODUCTION_ENV, "RXLOGIC_RATE_LIMIT_STORAGE_URI": "memory://"}
    with pytest.raises(ValueError, match="Redis"):
        build_security_settings(env)


def test_invalid_environment_and_proxy_hop_settings_are_rejected():
    with pytest.raises(ValueError, match="RXLOGIC_ENV"):
        build_security_settings({"RXLOGIC_ENV": "prod"})
    with pytest.raises(ValueError, match="TRUSTED_PROXY_HOPS"):
        build_security_settings({"RXLOGIC_TRUSTED_PROXY_HOPS": "many"})
    with pytest.raises(ValueError, match="TRUSTED_PROXY_HOPS"):
        build_security_settings({"RXLOGIC_TRUSTED_PROXY_HOPS": "11"})


def test_signed_session_cookie_round_trips_and_tampering_fails():
    key = b"k" * 32
    session_id = "7f9e2f3b-4dd8-4b2f-9c75-7a6b45a8d0e1"
    cookie = sign_session_id(session_id, key, issued_at=1_700_000_000)
    assert verify_session_cookie(cookie, key, now=1_700_000_100) == session_id
    tampered = cookie[:-1] + ("0" if cookie[-1] != "0" else "1")
    assert verify_session_cookie(tampered, key, now=1_700_000_100) is None
    assert verify_session_cookie("not-a-uuid", key) is None
    assert verify_session_cookie(cookie, b"d" * 32, now=1_700_000_100) is None


def test_signed_session_cookie_expires_and_rejects_far_future_timestamps():
    key = b"k" * 32
    session_id = "7f9e2f3b-4dd8-4b2f-9c75-7a6b45a8d0e1"
    issued_at = 1_700_000_000
    cookie = sign_session_id(session_id, key, issued_at=issued_at)
    assert verify_session_cookie(cookie, key, now=issued_at + 90 * 24 * 60 * 60) == session_id
    assert verify_session_cookie(cookie, key, now=issued_at + 90 * 24 * 60 * 60 + 1) is None
    future_cookie = sign_session_id(session_id, key, issued_at=issued_at + 120)
    assert verify_session_cookie(future_cookie, key, now=issued_at) is None


def test_sign_session_cookie_rejects_noncanonical_uuid():
    with pytest.raises(ValueError, match="canonical UUID"):
        sign_session_id("7F9E2F3B-4DD8-4B2F-9C75-7A6B45A8D0E1", b"k" * 32)


def test_security_preflight_passes_development_but_warns_about_process_local_limits():
    from services.security import security_preflight

    report = security_preflight({"RXLOGIC_ENV": "development", "RXLOGIC_RATE_LIMIT_STORAGE_URI": "memory://"})
    assert report["passed"] is True
    assert report["warnings"]


def test_security_preflight_production_requires_shared_services():
    from services.security import security_preflight

    report = security_preflight(PRODUCTION_ENV)
    assert report["passed"] is True
    assert report["checks"]["persistent_database_configured"] is True
    assert report["checks"]["shared_rate_limit_storage_configured"] is True


def test_security_preflight_reports_missing_production_secret():
    from services.security import security_preflight

    report = security_preflight({**PRODUCTION_ENV, "RXLOGIC_SESSION_SIGNING_KEY": ""})
    assert report["passed"] is False
    assert any("RXLOGIC_SESSION_SIGNING_KEY" in message for message in report["errors"])
