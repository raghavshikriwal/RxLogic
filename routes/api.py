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

from flask import Blueprint, Response, jsonify, request

from extensions import limiter
from models.exceptions import (
    ConstraintUnsatisfiableError,
    ExternalAPIError,
    InsufficientDataError,
    RxLogicError,
    SchemaValidationError,
    UnknownMedicationError,
)
from models.schemas import DailyPlan, Medication, TimingPreference
from services.llm_parser import parse_medications
from services.plan_log_service import get_recent_plans, log_plan
from services.reasoning_service import generate_daily_plan

api = Blueprint("api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)

# -- anonymous session scoping ------------------------------------------------
#
# Every plan a client creates, and every plan they can list back via
# GET /api/plans, is scoped to a server-minted anonymous session id -- not
# any real identity. Without this, PlanLog rows had no owner at all and
# GET /api/plans returned every plan ever logged by every visitor (a real
# data leak on a public deployment, not a hypothetical). See README §8.
#
# The session id travels as an httponly cookie rather than a header the
# frontend must remember to send: the app is served same-origin (app.py),
# so the browser attaches it automatically on every request once set, and
# no client-side wiring is needed to benefit from the fix.

SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365  # 1 year


def _resolve_session_id() -> tuple[str, bool]:
    """Returns (session_id, is_new).

    Reads the session id from the request's `session_id` cookie. Mints a
    fresh UUID4 if the cookie is absent *or* not a well-formed UUID (e.g.
    a tampered or corrupted cookie value) -- a bad cookie degrades to "new
    anonymous session" rather than a hard failure, so it can never turn
    into a 400 for a client that did nothing wrong.
    """
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if raw:
        try:
            uuid.UUID(raw)
        except ValueError:
            pass
        else:
            return raw, False
    return str(uuid.uuid4()), True


def _attach_session_cookie(response: Response, session_id: str) -> None:
    """Sets/refreshes the session cookie on every response so the browser's
    session survives for a full year of activity, not just until the first
    idle gap longer than the cookie's remaining lifetime."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        max_age=SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="Lax",
    )


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


def _try_log_plan(medications: list[Medication], plan: DailyPlan, source: str, session_id: str) -> None:
    """Best-effort persistence: a logging failure must never turn a
    successful plan response into a 500. The exception is swallowed
    from the caller's point of view, but never silently -- it's
    recorded with a full traceback (Section 6.3 auditability) so a
    broken audit trail is visible in ops/monitoring instead of
    disappearing without a trace."""
    try:
        log_plan(medications, plan, source=source, session_id=session_id)
    except Exception:
        logger.exception(
            "Failed to persist PlanLog row (source=%s, medication_count=%d); "
            "the /api/plan response still succeeded, but this plan is missing "
            "from the audit trail.",
            source,
            len(medications),
        )


# -- response serialization: typed DailyPlan -> JSON --------------------------


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
        "warnings": [
            {**asdict(w), "severity": w.severity.value}
            for w in plan.warnings
        ],
        "goal_trace": plan.goal_trace,
    }


# -- routes -------------------------------------------------------------------


@api.route("/health", methods=["GET"])
def health() -> tuple[dict[str, Any], int]:
    return jsonify({"status": "ok"}), 200


@api.route("/plan", methods=["POST"])
@limiter.limit("20 per minute")
def create_plan() -> tuple[Response, int]:
    payload = request.get_json(silent=True)
    if payload is None:
        raise SchemaValidationError(raw_output="<no body>", validation_errors="request body must be JSON")

    medications = _parse_medications(payload)
    plan = generate_daily_plan(medications)

    session_id, _ = _resolve_session_id()
    _try_log_plan(medications, plan, source="structured", session_id=session_id)

    response = jsonify(_serialize_plan(plan))
    _attach_session_cookie(response, session_id)
    return response, 200


@api.route("/plan/nl", methods=["POST"])
@limiter.limit("10 per minute")  # lower than /plan: this hits the LLM, not just the reasoning core
def create_plan_from_text() -> tuple[Response, int]:
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

    session_id, _ = _resolve_session_id()
    _try_log_plan(medications, plan, source="natural_language", session_id=session_id)

    response = jsonify(_serialize_plan(plan))
    _attach_session_cookie(response, session_id)
    return response, 200


@api.route("/plans", methods=["GET"])
@limiter.limit("30 per minute")
def list_plans() -> tuple[Response, int]:
    """Returns the *requesting session's* most recent logged plans, newest
    first (Section 6.3 auditability) -- never another session's history."""
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(limit, 100))  # clamp to a sane range

    session_id, is_new = _resolve_session_id()
    # A brand-new session id can't have any rows yet -- skip the query
    # entirely rather than asking the database a question we already
    # know the answer to.
    plans = [] if is_new else get_recent_plans(session_id=session_id, limit=limit)

    response = jsonify({"plans": plans})
    _attach_session_cookie(response, session_id)
    return response, 200


# -- error handling: every RxLogicError -> a specific, predictable response ---


@api.errorhandler(SchemaValidationError)
def handle_schema_validation_error(err: SchemaValidationError):
    return jsonify({"error": "schema_validation_error", "message": str(err)}), 400


@api.errorhandler(UnknownMedicationError)
def handle_unknown_medication_error(err: UnknownMedicationError):
    return jsonify({"error": "unknown_medication", "message": str(err)}), 422


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