"""Explicit, rate-limited external evidence retrieval endpoints (Task 16)."""
from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from extensions import limiter
from services.external_knowledge import ExternalKnowledgeService
from services.dailymed_mapping import preview_staged_dailymed_evidence

logger = logging.getLogger(__name__)
external_knowledge_api = Blueprint("external_knowledge_api", __name__, url_prefix="/api/external-knowledge")
_service = ExternalKnowledgeService()


@external_knowledge_api.get("/sources")
@limiter.limit("30 per minute")
def source_capabilities() -> tuple[Any, int]:
    from services.external_sources.registry import available_source_capabilities
    return jsonify({"sources": available_source_capabilities()}), 200


@external_knowledge_api.post("/search")
@limiter.limit("5 per minute")
def search_external_sources() -> tuple[Any, int]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid_request", "message": "A JSON request body is required."}), 400
    medication_name = payload.get("medication_name")
    sources = payload.get("sources")
    refresh = payload.get("refresh", False)
    if sources is not None and (not isinstance(sources, list) or not all(isinstance(x, str) for x in sources)):
        return jsonify({"error": "invalid_request", "message": "sources must be an array of source identifiers."}), 400
    if not isinstance(refresh, bool):
        return jsonify({"error": "invalid_request", "message": "refresh must be a boolean."}), 400
    try:
        result = _service.search(medication_name, sources, refresh=refresh)
    except ValueError as exc:
        return jsonify({"error": "invalid_request", "message": str(exc)}), 400
    return jsonify(result), 200

@external_knowledge_api.get("/evidence/<record_id>/dailymed-preview")
@limiter.limit("30 per minute")
def preview_dailymed_evidence(record_id: str):
    """Return a read-only, integrity-verified DailyMed section preview."""
    from services.evidence_review import EvidenceReviewError

    canonical_medication = request.args.get("canonical_medication", "")

    try:
        result = preview_staged_dailymed_evidence(
            record_id=record_id,
            canonical_medication=canonical_medication,
        )
        return jsonify(result), 200

    except EvidenceReviewError:
        logger.warning("DailyMed preview evidence unavailable or invalid")
        return jsonify({
            "error": "evidence_unavailable",
            "message": "The requested staged evidence could not be verified.",
        }), 404

    except ValueError:
        return jsonify({
            "error": "invalid_preview_request",
            "message": "The evidence record or medication preview request is invalid.",
        }), 400

    except Exception as exc:
        logger.error("DailyMed preview failed (%s)", type(exc).__name__)
        return jsonify({
            "error": "preview_unavailable",
            "message": "The DailyMed preview is temporarily unavailable.",
        }), 503

