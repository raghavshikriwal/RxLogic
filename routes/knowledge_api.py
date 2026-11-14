"""Read-only medication knowledge endpoints.

Thin HTTP layer over ``services.clinical_profile``. It contains no clinical
logic and no medication content: everything returned comes from the governed
knowledge datasets (an integrity-verified active release for approved
findings). Existing ``/api`` contracts are unchanged; these routes only add.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from flask import Blueprint, jsonify

from extensions import limiter
from services.clinical_profile import (
    KnowledgeView, UnknownMedicationLookup, build_catalog_overview, build_medication_profile,
)
from services.knowledge_release import DEFAULT_KNOWLEDGE_ROOT, KnowledgeReleaseError

knowledge_api = Blueprint("knowledge_api", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


def _load_view() -> KnowledgeView:
    configured = os.getenv("RXLOGIC_KNOWLEDGE_ROOT")
    return KnowledgeView.load(Path(configured) if configured else DEFAULT_KNOWLEDGE_ROOT)


@knowledge_api.route("/medications", methods=["GET"])
@limiter.limit("30 per minute")
def list_medications() -> tuple[Any, int]:
    """Every catalog medication identity with its evidence-assessment state."""
    return jsonify(build_catalog_overview(_load_view())), 200


@knowledge_api.route("/medications/<name>/clinical", methods=["GET"])
@limiter.limit("60 per minute")
def medication_clinical_profile(name: str) -> tuple[Any, int]:
    """Evidence-traceable clinical profile for one medication (name or alias)."""
    return jsonify(build_medication_profile(_load_view(), name)), 200


@knowledge_api.errorhandler(UnknownMedicationLookup)
def _unknown_medication(err: UnknownMedicationLookup):
    return jsonify({
        "error": "unknown_medication",
        "message": f"'{err.name}' is not in the RxLogic medication catalog.",
        "unknown_medications": [err.name],
    }), 404


@knowledge_api.errorhandler(KnowledgeReleaseError)
def _release_unavailable(err: KnowledgeReleaseError):
    logger.warning("Medication knowledge unavailable (%s)", type(err).__name__)
    return jsonify({
        "error": "approved_knowledge_unavailable",
        "message": "The configured approved knowledge release is unavailable.",
    }), 503


@knowledge_api.errorhandler(ValueError)
def _configuration_error(err: ValueError):
    # The detail (which may contain file paths) goes to the server log only.
    logger.warning("Medication knowledge configuration error: %s", err)
    return jsonify({
        "error": "configuration_error",
        "message": "The medication knowledge configuration is invalid or unreadable.",
    }), 503
