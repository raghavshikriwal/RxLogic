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
    assert body["error"] == "external_api_error"


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
def test_create_plan_logging_failure_does_not_break_success_response(mock_log_plan, client):
    mock_log_plan.side_effect = RuntimeError("database is unreachable")

    payload = {"medications": [{"name": "Metformin", "frequency_per_day": 1}]}
    response = client.post("/api/plan", json=payload)

    assert response.status_code == 200
    assert len(response.get_json()["entries"]) == 1
    mock_log_plan.assert_called_once()


# ---------------------------------------------------------------------------
# GET /api/plans
# ---------------------------------------------------------------------------

def test_list_plans_endpoint_returns_the_plan_just_created(client):
    payload = {"medications": [{"name": "Amoxicillin", "frequency_per_day": 1}]}
    create_response = client.post("/api/plan", json=payload)
    assert create_response.status_code == 200

    # newest-first ordering (plan_log_service.get_recent_plans) means the
    # plan created above must be the first row with limit=1, regardless of
    # how many other plans earlier tests logged to the shared test database.
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
    # neither should error even though the underlying table has far fewer rows.
    too_low = client.get("/api/plans?limit=0")
    too_high = client.get("/api/plans?limit=500")

    assert too_low.status_code == 200
    assert len(too_low.get_json()["plans"]) == 1
    assert too_high.status_code == 200