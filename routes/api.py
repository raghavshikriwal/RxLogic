"""
HTTP API layer — thin translation between JSON and the typed schema
boundary (models/schemas.py). This file contains zero reasoning logic;
every request is validated into typed objects, handed to
services.reasoning_service, and the typed result is serialized back
out. Section 4.1: the schema boundary is enforced here too, not just
between the LLM and the reasoning core.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict
from typing import Any

from flask import Blueprint, jsonify, request

from extensions import limiter
from models.exceptions import (
    ConstraintUnsatisfiableError,
    ExternalAPIError,
    InsufficientDataError,
    RxLogicError,
    SchemaValidationError,
    UnknownMedicationError,
)
from models.schemas import (
    Coverage,
    DailyPlan,
    FoodGuidance,
    Interaction,
    Medication,
    NameResolution,
    TimingPreference,
)
from services.llm_parser import parse_medications
from services.plan_log_service import get_recent_plans, log_plan
from services.reasoning_service import generate_daily_plan

api = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)

SESSION_COOKIE_NAME = "rxlogic_sid"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365
_SESSION_ENVIRON_KEY = "rxlogic.session"

# -- anonymous session resolution ---------------------------------------------


def _is_valid_session_id(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


def _resolve_session() -> tuple[str, bool]:
    """Returns (session_id, is_new) for this request, minting a UUID if the
    cookie is missing or malformed. Cached on the WSGI environ so it is
    strictly per-request (flask.g can outlive a request under a preserved
    test context). The cookie carries no identity, only a history scope."""
    if _SESSION_ENVIRON_KEY not in request.environ:
        cookie_value = request.cookies.get(SESSION_COOKIE_NAME, "")
        is_new = not _is_valid_session_id(cookie_value)
        session_id = str(uuid.uuid4()) if is_new else cookie_value
        request.environ[_SESSION_ENVIRON_KEY] = (session_id, is_new)
    return request.environ[_SESSION_ENVIRON_KEY]


def _get_session_id() -> str:
    return _resolve_session()[0]


@api.after_request
def _persist_session_cookie(response):
    session_id, is_new = request.environ.get(_SESSION_ENVIRON_KEY, (None, False))
    if is_new:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure,
        )
    return response

# -- request parsing: JSON -> typed Medication objects -----------------------


def _parse_medication(raw: dict[str, Any]) -> Medication:
    try:
        name = raw["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("'name' must be a non-empty string")

        timing_raw = raw.get("timing_preference", TimingPreference.NO_PREFERENCE.value)
        timing_preference = TimingPreference(timing_raw)

        return Medication(
            name=name,
            dosage_mg=raw.get("dosage_mg"),
            frequency_per_day=int(raw.get("frequency_per_day", 1)),
            timing_preference=timing_preference,
            with_food=raw.get("with_food"),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise SchemaValidationError(raw_output=str(raw), validation_errors=str(exc)) from exc


def _parse_medications(payload: dict[str, Any]) -> list[Medication]:
    raw_medications = payload.get("medications")
    if not isinstance(raw_medications, list):
        raise SchemaValidationError(
            raw_output=str(payload),
            validation_errors="'medications' must be a JSON array",
        )
    return [_parse_medication(m) for m in raw_medications]


# -- best-effort logging helper -----------------------------------------------


def _try_log_plan(medications: list[Medication], plan: DailyPlan, source: str) -> None:
    """Best-effort persistence: a logging failure must never turn a
    successful plan response into a 500. The exception is swallowed
    from the caller's point of view, but never silently -- it's
    recorded with a full traceback (Section 6.3 auditability) so a
    broken audit trail is visible in ops/monitoring instead of
    disappearing without a trace."""
    try:
        log_plan(medications, plan, source=source, session_id=_get_session_id())
    except Exception:
        logger.exception(
            "Failed to persist PlanLog row (source=%s, medication_count=%d); "
            "the /api/plan response still succeeded, but this plan is missing "
            "from the audit trail.",
            source,
            len(medications),
        )


# -- response serialization: typed DailyPlan -> JSON --------------------------


def _serialize_coverage(coverage: Coverage | None) -> dict[str, Any] | None:
    if coverage is None:
        return None
    return {
        "checked": coverage.checked,
        "total": coverage.total,
        "is_complete": coverage.is_complete,
        "unchecked": list(coverage.unchecked),
        "summary": coverage.summary,
    }


def _serialize_resolution(resolution: NameResolution) -> dict[str, Any]:
    return {
        "input_name": resolution.input_name,
        "resolved_to": resolution.canonical_name,
        "match": resolution.match.value,
        "score": resolution.score,
    }


def _serialize_food_guidance(guidance: FoodGuidance) -> dict[str, Any]:
    return {
        "medication": guidance.medication,
        "requirement": guidance.requirement.value,
        "status": guidance.status.value,
        "note": guidance.note,
        "source": guidance.source,
    }


def _serialize_interaction(interaction: Interaction) -> dict[str, Any]:
    return {
        **asdict(interaction),
        "severity": interaction.severity.value,
        "evidence": interaction.evidence.value,
    }


def _serialize_plan(plan: DailyPlan) -> dict[str, Any]:
    return {
        "entries": [
            {
                "medication": e.medication,
                "scheduled_time": e.scheduled_time.strftime("%H:%M"),
                "reasoning": e.reasoning,
                "constraint_ids": e.constraint_ids,
            }
            for e in plan.entries
        ],
        "warnings": [_serialize_interaction(w) for w in plan.warnings],
        "goal_trace": plan.goal_trace,
        "coverage": _serialize_coverage(plan.coverage),
        "name_resolutions": [_serialize_resolution(r) for r in plan.resolutions],
        "food_guidance": [_serialize_food_guidance(g) for g in plan.food_guidance],
    }


# -- routes -------------------------------------------------------------------


@api.route("/health", methods=["GET"])
def health() -> tuple[dict[str, Any], int]:
    return jsonify({"status": "ok"}), 200


@api.route("/plan", methods=["POST"])
@limiter.limit("20 per minute")
def create_plan() -> tuple[dict[str, Any], int]:
    payload = request.get_json(silent=True)
    if payload is None:
        raise SchemaValidationError(raw_output="<no body>", validation_errors="request body must be JSON")

    medications = _parse_medications(payload)
    plan = generate_daily_plan(medications)
    _try_log_plan(medications, plan, source="structured")
    return jsonify(_serialize_plan(plan)), 200


@api.route("/plan/nl", methods=["POST"])
@limiter.limit("10 per minute")  # lower than /plan: this hits the LLM, not just the reasoning core
def create_plan_from_text() -> tuple[dict[str, Any], int]:
    """
    Free-text entry point (Layer 1, Section 4.1). Parses natural language
    into the same typed Medication schema /plan expects, then runs the
    identical reasoning pipeline. Proves Section 4.3: this route is a thin
    convenience wrapper -- remove it entirely and /plan still fully works.
    """
    payload = request.get_json(silent=True)
    if payload is None:
        raise SchemaValidationError(raw_output="<no body>", validation_errors="request body must be JSON")

    user_text = payload.get("text")
    if not isinstance(user_text, str) or not user_text.strip():
        raise SchemaValidationError(raw_output=str(payload), validation_errors="'text' must be a non-empty string")

    medications = parse_medications(user_text)
    plan = generate_daily_plan(medications)
    _try_log_plan(medications, plan, source="natural_language")
    return jsonify(_serialize_plan(plan)), 200


@api.route("/plans", methods=["GET"])
@limiter.limit("30 per minute")
def list_plans() -> tuple[dict[str, Any], int]:
    """Returns the caller's own most recent logged plans, newest first (Section 6.3 auditability)."""
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(limit, 100))  # clamp to a sane range
    return jsonify({"plans": get_recent_plans(session_id=_get_session_id(), limit=limit)}), 200


# -- error handling: every RxLogicError -> a specific, predictable response ---


@api.errorhandler(SchemaValidationError)
def handle_schema_validation_error(err: SchemaValidationError):
    return jsonify({"error": "schema_validation_error", "message": str(err)}), 400


@api.errorhandler(UnknownMedicationError)
def handle_unknown_medication_error(err: UnknownMedicationError):
    return jsonify({
        "error": "unknown_medication",
        "message": str(err),
        "unknown_medications": list(err.medication_names),
    }), 422


@api.errorhandler(InsufficientDataError)
def handle_insufficient_data_error(err: InsufficientDataError):
    return jsonify({"error": "insufficient_data", "message": str(err)}), 422


@api.errorhandler(ConstraintUnsatisfiableError)
def handle_constraint_unsatisfiable_error(err: ConstraintUnsatisfiableError):
    return jsonify({"error": "no_feasible_schedule", "message": str(err)}), 422


@api.errorhandler(ExternalAPIError)
def handle_external_api_error(err: ExternalAPIError):
    # Ollama failures (Layer 1, LLM parser) and RxNav/openFDA failures
    # (drug-data client) both raise ExternalAPIError, but they are
    # different failure modes for the user: one means "the AI parser
    # is down, try structured input instead", the other means "drug
    # lookup is temporarily unavailable". Keep them distinguishable
    # past this handler instead of collapsing both into one code.
    error_code = "llm_api_error" if err.api_name == "Ollama" else "external_api_error"
    return jsonify({"error": error_code, "message": str(err)}), 502


@api.errorhandler(RxLogicError)
def handle_rxlogic_error(err: RxLogicError):
    # fail-safe catch-all for any domain error not mapped above
    return jsonify({"error": "reasoning_error", "message": str(err)}), 422