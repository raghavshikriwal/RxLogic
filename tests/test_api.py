"""
Tests for routes/api.py + app.py

Covers: /api/health, a successful /api/plan round-trip through Flask's
test client, that each domain exception maps to its documented HTTP
status code, and the /api/plan/nl free-text entry point (with
llm_parser mocked so no live Ollama instance is required).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app
from models.exceptions import (
    ConstraintUnsatisfiableError,
    ExternalAPIError,
    RxLogicError,
    UnknownMedicationError,
)
from models.schemas import Medication


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_root_route_returns_friendly_error_when_frontend_not_built(client, tmp_path):
    """When frontend/dist doesn't exist (e.g. a fresh clone before `npm
    run build`), the root route should degrade to a clear JSON error
    instead of crashing -- see app.py's `_register_frontend_route`."""
    missing_dist = tmp_path / "dist-not-built"
    with patch("app.FRONTEND_DIST", missing_dist):
        response = client.get("/")

    assert response.status_code == 503
    assert response.get_json()["error"] == "frontend_not_built"


def test_root_route_serves_built_frontend_index(client, tmp_path):
    """When frontend/dist exists, the root route should serve its
    index.html rather than any API JSON payload."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>RxLogic</body></html>")

    with patch("app.FRONTEND_DIST", dist):
        response = client.get("/")

    assert response.status_code == 200
    assert b"RxLogic" in response.data



def test_create_plan_success(client):
    payload = {
        "medications": [
            {"name": "Warfarin", "frequency_per_day": 1},
            {"name": "Aspirin", "frequency_per_day": 1},
        ]
    }
    response = client.post("/api/plan", json=payload)
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["entries"]) == 2
    assert body["warnings"]
    assert body["warnings"][0]["severity"] == "severe"
    assert {body["warnings"][0]["medication_a"], body["warnings"][0]["medication_b"]} == {"warfarin", "aspirin"}
    assert len(body["goal_trace"]) == 2


def test_create_plan_missing_body_returns_400(client):
    response = client.post("/api/plan", data="not json", content_type="text/plain")
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"] == "schema_validation_error"


def test_create_plan_missing_name_field_returns_400(client):
    payload = {"medications": [{"frequency_per_day": 1}]}
    response = client.post("/api/plan", json=payload)
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"] == "schema_validation_error"


def test_create_plan_blank_name_string_returns_400(client):
    # distinct from the missing-key case above: 'name' is present but is an
    # empty/whitespace-only string, which must fail the same validation.
    payload = {"medications": [{"name": "   "}]}
    response = client.post("/api/plan", json=payload)
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"] == "schema_validation_error"


def test_create_plan_invalid_timing_preference_returns_400(client):
    payload = {"medications": [{"name": "Metformin", "timing_preference": "not_a_real_value"}]}
    response = client.post("/api/plan", json=payload)

    assert response.status_code == 400


def test_create_plan_empty_medication_list_returns_422(client):
    response = client.post("/api/plan", json={"medications": []})
    body = response.get_json()

    assert response.status_code == 422
    assert body["error"] == "insufficient_data"


def test_medications_field_wrong_type_returns_400(client):
    response = client.post("/api/plan", json={"medications": "not a list"})
    assert response.status_code == 400


@patch("routes.api.parse_medications")
def test_create_plan_from_text_success(mock_parse, client):
    mock_parse.return_value = [
        Medication(name="warfarin", frequency_per_day=1),
        Medication(name="aspirin", frequency_per_day=1),
    ]

    response = client.post("/api/plan/nl", json={"text": "I take warfarin and just started aspirin"})
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["entries"]) == 2
    assert body["warnings"][0]["severity"] == "severe"
    mock_parse.assert_called_once_with("I take warfarin and just started aspirin")


def test_create_plan_from_text_missing_text_field_returns_400(client):
    response = client.post("/api/plan/nl", json={})
    assert response.status_code == 400


def test_create_plan_from_text_missing_body_returns_400(client):
    # mirrors test_create_plan_missing_body_returns_400 for the /plan route --
    # /plan/nl has its own identical "payload is None" check (routes/api.py)
    # that was previously exercised only on the sibling endpoint.
    response = client.post("/api/plan/nl", data="not json", content_type="text/plain")
    body = response.get_json()

    assert response.status_code == 400
    assert body["error"] == "schema_validation_error"


@patch("routes.api.parse_medications")
def test_create_plan_from_text_ollama_down_returns_502(mock_parse, client):
    mock_parse.side_effect = ExternalAPIError(api_name="Ollama", status_code=None)

    response = client.post("/api/plan/nl", json={"text": "metformin twice a day"})
    body = response.get_json()

    assert response.status_code == 502
    assert body["error"] == "llm_api_error"


# ---------------------------------------------------------------------------
# Error-handler branches not reachable via the current real reasoning
# pipeline (Section 9 fail-safes: defensive handlers for error types the
# pipeline doesn't raise today but the API contract still documents).
# generate_daily_plan is mocked directly so each handler is verified in
# isolation from whether anything in the pipeline currently raises it.
# ---------------------------------------------------------------------------

@patch("routes.api.generate_daily_plan")
def test_create_plan_unknown_medication_error_returns_422(mock_generate, client):
    mock_generate.side_effect = UnknownMedicationError(medication_name="not-a-real-drug")

    response = client.post("/api/plan", json={"medications": [{"name": "not-a-real-drug"}]})
    body = response.get_json()

    assert response.status_code == 422
    assert body["error"] == "unknown_medication"


@patch("routes.api.generate_daily_plan")
def test_create_plan_constraint_unsatisfiable_returns_422(mock_generate, client):
    mock_generate.side_effect = ConstraintUnsatisfiableError(conflicting_constraints=["warfarin", "aspirin"])

    response = client.post("/api/plan", json={"medications": [{"name": "Warfarin"}, {"name": "Aspirin"}]})
    body = response.get_json()

    assert response.status_code == 422
    assert body["error"] == "no_feasible_schedule"


@patch("routes.api.generate_daily_plan")
def test_create_plan_generic_rxlogic_error_falls_back_to_catch_all_handler(mock_generate, client):
    # a bare RxLogicError (not one of the specific subclasses) must still be
    # mapped to a predictable response rather than surfacing as a 500.
    mock_generate.side_effect = RxLogicError("unclassified reasoning failure")

    response = client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    body = response.get_json()

    assert response.status_code == 422
    assert body["error"] == "reasoning_error"


# ---------------------------------------------------------------------------
# Best-effort logging (_try_log_plan): a broken log write must never turn a
# successful plan into a failed response.
# ---------------------------------------------------------------------------

@patch("routes.api.log_plan")
def test_create_plan_logging_failure_does_not_break_success_response(mock_log_plan, client, caplog):
    mock_log_plan.side_effect = RuntimeError("database is unreachable")

    payload = {"medications": [{"name": "Metformin", "frequency_per_day": 1}]}
    with caplog.at_level("ERROR", logger="routes.api"):
        response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    assert len(response.get_json()["entries"]) == 1
    mock_log_plan.assert_called_once()

    # the failure must not vanish silently -- it should land in the logs
    # with enough context (source, medication count) to investigate later.
    assert len(caplog.records) == 1
    logged = caplog.records[0]
    assert logged.levelname == "ERROR"
    assert "structured" in logged.getMessage()
    assert logged.exc_info is not None  # traceback must be attached, not just a message


# ---------------------------------------------------------------------------
# GET /api/plans
# ---------------------------------------------------------------------------

def test_list_plans_endpoint_returns_the_plan_just_created(client):
    payload = {"medications": [{"name": "Amoxicillin", "frequency_per_day": 1}]}
    create_response = client.post("/api/plan", json=payload)
    assert create_response.status_code == 200

    # newest-first ordering (plan_log_service.get_recent_plans), scoped to
    # this client's own session cookie -- the plan created above must be
    # the first row with limit=1, regardless of how many other plans
    # earlier tests (running under their own, different session ids)
    # logged to the shared test database.
    list_response = client.get("/api/plans?limit=1")
    body = list_response.get_json()

    assert list_response.status_code == 200
    assert len(body["plans"]) == 1
    logged_plan = body["plans"][0]
    assert logged_plan["source"] == "structured"
    assert any(m["name"] == "Amoxicillin" for m in logged_plan["input_medications"])
    assert "id" in logged_plan and "created_at" in logged_plan


def test_list_plans_limit_param_is_respected(client):
    client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    client.post("/api/plan", json={"medications": [{"name": "Omeprazole"}]})

    response = client.get("/api/plans?limit=2")
    body = response.get_json()

    assert response.status_code == 200
    assert len(body["plans"]) == 2


def test_list_plans_limit_is_clamped_to_a_sane_range(client):
    # limit=0 clamps up to 1, limit=500 clamps down to 100 (routes/api.py);
    # neither should error. Create one plan first so this session has
    # something to clamp against.
    client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})

    too_low = client.get("/api/plans?limit=0")
    too_high = client.get("/api/plans?limit=500")

    assert too_low.status_code == 200
    assert len(too_low.get_json()["plans"]) == 1
    assert too_high.status_code == 200


# ---------------------------------------------------------------------------
# Anonymous session scoping (P1 privacy fix): GET /api/plans must return
# only the requesting session's own plans, never another session's.
# ---------------------------------------------------------------------------


def test_plans_are_scoped_to_the_requesting_session():
    """Two independent 'browsers' (separate test clients, each with its own
    cookie jar) must not be able to see each other's logged plans -- this
    is the regression test for the original data-leak bug."""
    app = create_app()
    app.config["TESTING"] = True

    # Plain (non-context-manager) test clients on purpose: `with
    # app.test_client() as c:` preserves request context after each call,
    # which two interleaved clients on the same app fight over and can
    # corrupt Flask's context stack. Nothing here needs request-context
    # preservation -- only the response objects are inspected.
    browser_a = app.test_client()
    browser_b = app.test_client()

    create_a = browser_a.post("/api/plan", json={"medications": [{"name": "Lisinopril"}]})
    create_b = browser_b.post("/api/plan", json={"medications": [{"name": "Atorvastatin"}]})
    assert create_a.status_code == 200
    assert create_b.status_code == 200

    plans_a = browser_a.get("/api/plans").get_json()["plans"]
    plans_b = browser_b.get("/api/plans").get_json()["plans"]

    medications_a = {m["name"] for p in plans_a for m in p["input_medications"]}
    medications_b = {m["name"] for p in plans_b for m in p["input_medications"]}

    assert "Lisinopril" in medications_a
    assert "Atorvastatin" not in medications_a
    assert "Atorvastatin" in medications_b
    assert "Lisinopril" not in medications_b


def test_list_plans_with_no_session_cookie_returns_empty_not_everyone_elses(client):
    # A client that has never created a plan (no session cookie yet) must
    # see an empty list -- never a default that leaks other sessions' data.
    response = client.get("/api/plans")
    body = response.get_json()

    assert response.status_code == 200
    assert body["plans"] == []


def test_create_plan_sets_a_session_cookie(client):
    response = client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    assert "session_id" in response.headers.get("Set-Cookie", "")


def test_repeat_requests_from_the_same_client_reuse_the_same_session(client):
    first = client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    second = client.post("/api/plan", json={"medications": [{"name": "Omeprazole"}]})
    assert first.status_code == 200 and second.status_code == 200

    plans = client.get("/api/plans?limit=10").get_json()["plans"]
    medications = {m["name"] for p in plans for m in p["input_medications"]}
    assert {"Metformin", "Omeprazole"}.issubset(medications)


def test_tampered_session_cookie_degrades_to_a_new_session_not_a_400(client):
    # A garbage/corrupted cookie value must never turn into a hard failure
    # for the client -- it should just fall back to a fresh anonymous session.
    client.set_cookie("session_id", "not-a-valid-uuid", domain="localhost")
    response = client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})

    assert response.status_code == 200
    new_cookie = response.headers.get("Set-Cookie", "")
    assert "not-a-valid-uuid" not in new_cookie