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
    assert body["warnings"][0]["evidence"] == "strong"
    assert {body["warnings"][0]["medication_a"], body["warnings"][0]["medication_b"]} == {"warfarin", "aspirin"}
    assert len(body["goal_trace"]) == 2
    assert body["clinical_assessment"]["clinical_use_permitted"] is False
    assert body["clinical_assessment"]["dosage_safety"]["patient_specific_dosing_generated"] is False



def test_patient_context_is_validated_and_not_required(client):
    response = client.post("/api/plan", json={
        "medications": [{"name": "Metformin"}],
        "patient_context": {"foods": ["grapefruit"], "conditions": ["kidney disease"]},
    })
    assert response.status_code == 200
    body = response.get_json()
    assert "clinical_assessment" in body
    assert body["clinical_assessment"]["clinical_use_permitted"] is False


def test_patient_context_rejects_unknown_fields(client):
    response = client.post("/api/plan", json={
        "medications": [{"name": "Metformin"}],
        "patient_context": {"allergies": ["penicillin"]},
    })
    assert response.status_code == 400
    assert response.get_json()["error"] == "schema_validation_error"

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
def test_create_plan_from_text_ollama_down_returns_llm_api_error_502(mock_parse, client):
    mock_parse.side_effect = ExternalAPIError(api_name="Ollama", status_code=None)

    response = client.post("/api/plan/nl", json={"text": "metformin twice a day"})
    body = response.get_json()

    assert response.status_code == 502
    assert body["error"] == "llm_api_error"


@patch("routes.api.parse_medications")
def test_non_llm_external_api_failure_keeps_external_api_error_code(mock_parse, client):
    mock_parse.side_effect = ExternalAPIError(api_name="RxNav", status_code=503)

    response = client.post("/api/plan/nl", json={"text": "metformin twice a day"})

    assert response.status_code == 502
    assert response.get_json()["error"] == "external_api_error"


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
    assert body["unknown_medications"] == ["not-a-real-drug"]


def test_create_plan_unknown_medication_is_rejected_by_the_real_pipeline(client):
    # No mocking: proves the reasoning pipeline itself raises, instead of
    # returning an all-clear plan for a drug the knowledge base doesn't cover.
    response = client.post(
        "/api/plan",
        json={"medications": [{"name": "Warfarin"}, {"name": "Zolpidem"}]},
    )
    body = response.get_json()

    assert response.status_code == 422
    assert body["error"] == "unknown_medication"
    assert body["unknown_medications"] == ["Zolpidem"]


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
    client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    client.post("/api/plan", json={"medications": [{"name": "Omeprazole"}]})

    too_low = client.get("/api/plans?limit=0")
    too_high = client.get("/api/plans?limit=500")

    assert too_low.status_code == 200
    assert len(too_low.get_json()["plans"]) == 1
    assert too_high.status_code == 200


def test_list_plans_is_scoped_to_the_callers_session(client):
    client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})

    with client.application.test_client() as other_client:
        assert other_client.get("/api/plans").get_json()["plans"] == []

    assert len(client.get("/api/plans").get_json()["plans"]) == 1


def test_malformed_session_cookie_is_replaced_not_trusted(client):
    client.set_cookie("rxlogic_sid", "not-a-uuid")

    response = client.get("/api/plans")

    assert response.status_code == 200
    assert "rxlogic_sid=" in response.headers["Set-Cookie"]
    assert "not-a-uuid" not in response.headers["Set-Cookie"]


def test_create_plan_response_includes_coverage_summary(client):
    response = client.post(
        "/api/plan",
        json={"medications": [{"name": "Warfarin"}, {"name": "Aspirin"}]},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["coverage"] == {
        "checked": 2,
        "total": 2,
        "is_complete": True,
        "unchecked": [],
        "identity_only": [],
        "summary": "2 of 2 drugs checked",
    }


def test_paracetamol_is_recognized_but_reported_as_identity_only(client):
    response = client.post("/api/plan", json={"medications": [{"name": "paracetamol"}]})
    body = response.get_json()
    assert response.status_code == 200
    assert body["name_resolutions"][0]["resolved_to"] == "acetaminophen"
    assert body["coverage"]["identity_only"] == ["acetaminophen"]


def test_create_plan_reports_name_resolutions_for_brand_names(client):
    response = client.post(
        "/api/plan",
        json={"medications": [{"name": "Coumadin"}, {"name": "asprin"}]},
    )
    body = response.get_json()

    assert response.status_code == 200
    assert body["coverage"]["is_complete"] is True
    assert body["name_resolutions"] == [
        {"input_name": "Coumadin", "resolved_to": "warfarin", "match": "alias", "score": 1.0},
        {"input_name": "asprin", "resolved_to": "aspirin", "match": "fuzzy", "score": 0.92},
    ]


def test_create_plan_without_corrections_returns_empty_name_resolutions(client):
    response = client.post("/api/plan", json={"medications": [{"name": "Warfarin"}]})

    assert response.get_json()["name_resolutions"] == []


def test_create_plan_exposes_order_aware_separation(client):
    payload = {"medications": [{"name": "Aspirin"}, {"name": "Ibuprofen"}]}

    response = client.post("/api/plan", json=payload)
    warning = response.get_json()["warnings"][0]

    assert response.status_code == 200
    assert warning["ordering"] == {"anchor": "aspirin", "after_minutes": 30, "before_minutes": 480}
    assert warning["separation_minutes"] is None


def test_create_plan_reports_no_separation_when_the_rule_has_none(client):
    payload = {"medications": [{"name": "Warfarin"}, {"name": "Aspirin"}]}

    response = client.post("/api/plan", json=payload)

    warning = response.get_json()["warnings"][0]
    assert warning["separation_minutes"] is None
    assert warning["ordering"] is None


def test_create_plan_reports_food_guidance(client):
    response = client.post("/api/plan", json={"medications": [{"name": "Metformin"}]})
    body = response.get_json()

    assert response.status_code == 200
    assert body["food_guidance"] == [
        {
            "medication": "metformin",
            "requirement": "with_food",
            "status": "informational",
            "note": "Not applied: this rule requires clinical review.",
            "source": "",
            "rule_id": "FOOD-METFORMIN",
            "evidence_source_ids": ["SRC-LEGACY-C00D96B655"],
            "review_status": "needs_clinical_review",
        }
    ]


def test_create_plan_without_food_rules_returns_empty_food_guidance(client):
    response = client.post("/api/plan", json={"medications": [{"name": "Aspirin"}]})

    assert response.get_json()["food_guidance"] == []


def test_knowledge_status_reports_development_mode(client, monkeypatch):
    monkeypatch.delenv("RXLOGIC_KNOWLEDGE_MODE", raising=False)
    response = client.get("/api/knowledge/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mode"] == "legacy_development"
    assert payload["clinical_use_permitted"] is False


def test_knowledge_status_fails_closed_when_active_release_missing(client, monkeypatch, tmp_path):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "active_release")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_ROOT", str(tmp_path))
    response = client.get("/api/knowledge/status")
    assert response.status_code == 503
    assert response.get_json()["error"] == "approved_knowledge_unavailable"


def test_knowledge_status_rejects_unknown_mode(client, monkeypatch):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "automatic")
    response = client.get("/api/knowledge/status")
    assert response.status_code == 503
    assert response.get_json()["status"] == "invalid_configuration"


def test_plan_endpoint_fails_closed_when_active_release_is_missing(client, monkeypatch, tmp_path):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "active_release")
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_ROOT", str(tmp_path))
    response = client.post("/api/plan", json={"medications": [{"name": "Aspirin"}]})
    assert response.status_code == 503
    assert response.get_json()["error"] == "approved_knowledge_unavailable"


def test_plan_endpoint_rejects_unknown_runtime_mode(client, monkeypatch):
    monkeypatch.setenv("RXLOGIC_KNOWLEDGE_MODE", "automatic")
    response = client.post("/api/plan", json={"medications": [{"name": "Aspirin"}]})
    assert response.status_code == 503
    assert response.get_json()["error"] == "invalid_knowledge_configuration"


def test_non_object_json_payload_returns_schema_error(client):
    response = client.post("/api/plan", json=[{"name": "Metformin"}])
    assert response.status_code == 400
    assert response.get_json()["error"] == "schema_validation_error"


def test_medication_batch_limit_is_enforced(client):
    response = client.post("/api/plan", json={"medications": [{"name": f"Drug {i}"} for i in range(26)]})
    assert response.status_code == 400
    assert "at most 25" in response.get_json()["message"]


@pytest.mark.parametrize("medication", [
    {"name": "Metformin", "dosage_mg": -1},
    {"name": "Metformin", "dosage_mg": float("nan")},
    {"name": "Metformin", "frequency_per_day": 0},
    {"name": "Metformin", "frequency_per_day": 7},
    {"name": "Metformin", "frequency_per_day": True},
    {"name": "Metformin", "with_food": "yes"},
    {"name": "M" * 121},
    {"name": "Metformin", "unexpected": "value"},
])
def test_medication_field_bounds_are_enforced(client, medication):
    response = client.post("/api/plan", json={"medications": [medication]})
    assert response.status_code == 400
    assert response.get_json()["error"] == "schema_validation_error"


def test_natural_language_input_length_is_bounded(client):
    with patch("routes.api.parse_medications") as parse:
        response = client.post("/api/plan/nl", json={"text": "x" * 4001})
    assert response.status_code == 400
    parse.assert_not_called()


# ---------------------------------------------------------------------------
# Task 16 — DailyMed evidence preview API
# ---------------------------------------------------------------------------

@patch("routes.external_knowledge_api.preview_staged_dailymed_evidence")
def test_dailymed_preview_api_success(mock_preview, client):
    mock_preview.return_value = {
        "schema": "rxlogic.dailymed_section_preview.v1",
        "medication": "Metformin",
        "preview_count": 1,
        "mapped_count": 1,
        "unmapped_count": 0,
        "previews": [],
        "evidence": {
            "record_id": "EVD-DM-001",
            "review_status": "pending_clinical_review",
            "promotion_status": "staged_only",
            "metadata_integrity": "verified",
        },
        "governance": {
            "is_clinical_assertion": False,
            "creates_curation_record": False,
            "requires_human_review": True,
            "can_be_promoted": False,
        },
    }

    response = client.get(
        "/api/external-knowledge/evidence/EVD-DM-001/dailymed-preview"
        "?canonical_medication=Metformin"
    )

    body = response.get_json()

    assert response.status_code == 200
    assert body["medication"] == "Metformin"
    assert body["evidence"]["review_status"] == "pending_clinical_review"
    assert body["evidence"]["promotion_status"] == "staged_only"
    assert body["governance"]["is_clinical_assertion"] is False
    assert body["governance"]["creates_curation_record"] is False
    assert body["governance"]["requires_human_review"] is True
    assert body["governance"]["can_be_promoted"] is False

    mock_preview.assert_called_once_with(
        record_id="EVD-DM-001",
        canonical_medication="Metformin",
    )


@patch("routes.external_knowledge_api.preview_staged_dailymed_evidence")
def test_dailymed_preview_unknown_evidence_returns_404(mock_preview, client):
    from services.evidence_review import EvidenceReviewError

    mock_preview.side_effect = EvidenceReviewError("internal evidence path")

    response = client.get(
        "/api/external-knowledge/evidence/UNKNOWN/dailymed-preview"
        "?canonical_medication=Metformin"
    )

    assert response.status_code == 404
    body = response.get_json()
    assert body["error"] == "evidence_unavailable"
    assert "internal evidence path" not in str(body)


@patch("routes.external_knowledge_api.preview_staged_dailymed_evidence")
def test_dailymed_preview_invalid_request_returns_400(mock_preview, client):
    mock_preview.side_effect = ValueError("unsupported evidence payload")

    response = client.get(
        "/api/external-knowledge/evidence/EVD-INVALID/dailymed-preview"
        "?canonical_medication=Metformin"
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "invalid_preview_request"
    assert "unsupported evidence payload" not in str(body)


@patch("routes.external_knowledge_api.preview_staged_dailymed_evidence")
def test_dailymed_preview_unexpected_error_is_sanitized(mock_preview, client):
    mock_preview.side_effect = RuntimeError("C:\\private\\staging\\secret.json")

    response = client.get(
        "/api/external-knowledge/evidence/EVD-ERROR/dailymed-preview"
        "?canonical_medication=Metformin"
    )

    assert response.status_code == 503
    body = response.get_json()
    assert body["error"] == "preview_unavailable"
    assert "private" not in str(body)
    assert "secret.json" not in str(body)
