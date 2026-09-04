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
from models.exceptions import ExternalAPIError
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


@patch("routes.api.parse_medications")
def test_create_plan_from_text_ollama_down_returns_502(mock_parse, client):
    mock_parse.side_effect = ExternalAPIError(api_name="Ollama", status_code=None)

    response = client.post("/api/plan/nl", json={"text": "metformin twice a day"})
    body = response.get_json()

    assert response.status_code == 502
    assert body["error"] == "external_api_error"