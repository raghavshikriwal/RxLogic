from __future__ import annotations

from unittest.mock import patch

import pytest

from app import create_app
from services.security import verify_session_cookie


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def test_api_responses_include_security_and_no_store_headers(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "no-store" in response.headers["Cache-Control"]
    assert response.headers["Permissions-Policy"]


def test_history_cookie_is_signed_http_only_and_same_site(client):
    response = client.get("/api/plans")
    assert response.status_code == 200
    cookie_header = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie_header
    assert "SameSite=Lax" in cookie_header
    cookie = client.get_cookie("rxlogic_sid")
    assert cookie is not None
    assert verify_session_cookie(cookie.value, client.application.config["RXLOGIC_SESSION_SIGNING_KEY"])


def test_tampered_signed_history_cookie_is_replaced(client):
    client.get("/api/plans")
    cookie = client.get_cookie("rxlogic_sid")
    assert cookie is not None
    tampered = cookie.value[:-1] + ("0" if cookie.value[-1] != "0" else "1")
    client.set_cookie("rxlogic_sid", tampered)
    response = client.get("/api/plans")
    new_cookie = client.get_cookie("rxlogic_sid")
    assert response.status_code == 200
    assert new_cookie is not None
    assert new_cookie.value != tampered
    assert verify_session_cookie(new_cookie.value, client.application.config["RXLOGIC_SESSION_SIGNING_KEY"])


def test_production_cookie_is_secure(monkeypatch):
    monkeypatch.setenv("RXLOGIC_ENV", "production")
    monkeypatch.setenv("FLASK_DEBUG", "false")
    monkeypatch.setenv("RXLOGIC_SESSION_SIGNING_KEY", "p" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@db.invalid/rxlogic")
    monkeypatch.setenv("RXLOGIC_RATE_LIMIT_STORAGE_URI", "rediss://redis.invalid:6379/0")

    app = create_app()

    # Verify production security configuration without making a request
    # that would require an actual Redis service.
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["RXLOGIC_HSTS_ENABLED"] is True


def test_request_body_over_limit_returns_json_413(client):
    response = client.post("/api/plan", data=" " * 70000, content_type="application/json")
    assert response.status_code == 413
    assert response.is_json
    assert response.get_json()["error"] == "http_413"


def test_api_unexpected_errors_are_generic_and_do_not_leak_details(client):
    with patch("routes.api.generate_daily_plan", side_effect=RuntimeError("database password leaked")):
        response = client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    assert response.status_code == 500
    assert response.get_json() == {
        "error": "internal_server_error",
        "message": "An unexpected error occurred. Please try again later.",
    }


def test_html_response_has_content_security_policy(client, tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><html><body>RxLogic</body></html>", encoding="utf-8")
    monkeypatch.setattr("app.FRONTEND_DIST", dist)
    response = client.get("/")
    assert response.status_code == 200
    assert "Content-Security-Policy" in response.headers
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_unknown_api_path_returns_json_404_not_spa_fallback(client):
    response = client.get("/api/not-a-real-endpoint")
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["error"] == "http_404"


def test_rate_limit_storage_is_applied_from_each_app_configuration(monkeypatch):
    redis_uri = "rediss://redis.invalid:6379/0"
    monkeypatch.setenv("RXLOGIC_RATE_LIMIT_STORAGE_URI", redis_uri)
    app = create_app()
    assert app.config["RXLOGIC_RATE_LIMIT_STORAGE_URI"] == redis_uri
    assert app.config["RATELIMIT_STORAGE_URI"] == redis_uri
