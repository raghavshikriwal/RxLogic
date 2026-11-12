"""Controlled authoring and independent clinical review of knowledge candidates.

Task 06 stage 1 deliberately stops before publication: candidates and review
records are stored outside runtime datasets. Nothing in this module mutates the
active interaction/food rule files or makes a candidate available to runtime.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.evidence_review import (
    DEFAULT_STAGING_ROOT,
    EvidenceReviewError,
    inspect_evidence,
    list_review_queue,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CURATION_ROOT = PROJECT_ROOT / "knowledge" / "curation"
CANDIDATE_FILE = "candidates.jsonl"
DECISION_FILE = "candidate_decisions.jsonl"
CANDIDATE_TYPES = frozenset({
    "interaction_rule", "food_rule", "drug_food_interaction",
    "contraindication", "dosage_reference", "administration_instruction",
})
CLINICAL_APPROVER_ROLES = frozenset({"clinical_pharmacist", "physician"})
SEVERITIES = frozenset({"mild", "moderate", "severe", "unknown"})
EVIDENCE_STRENGTHS = frozenset({"strong", "moderate", "limited", "unknown"})
FOOD_REQUIREMENTS = frozenset({"with_food", "empty_stomach", "no_restriction"})


class CurationError(ValueError):
    """Raised when candidate authoring or clinical review is unsafe/invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_symlink():
        raise CurationError(f"{path.name} must not be a symbolic link")
    result = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                item = json.loads(line)
                if not isinstance(item, dict):
                    raise ValueError(f"line {number} is not an object")
                result.append(item)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise CurationError(f"Invalid {path.name}: {exc}") from exc
    return result


def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise CurationError(f"{path.name} must not be a symbolic link")
    data = (json.dumps(item, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _required_text(payload: dict[str, Any], key: str, limit: int = 4000) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise CurationError(f"{key} is required and must be at most {limit} characters")
    return value.strip()


def _validate_rule(rule_type: str, rule: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rule, dict):
        raise CurationError("rule must be a JSON object")
    normalized = dict(rule)
    if rule_type == "interaction_rule":
        a = _required_text(normalized, "medication_a", 200).lower()
        b = _required_text(normalized, "medication_b", 200).lower()
        if a == b:
            raise CurationError("interaction rule must identify two distinct medications")
        normalized["medication_a"], normalized["medication_b"] = a, b
        if normalized.get("severity") not in SEVERITIES:
            raise CurationError("severity must be mild, moderate, severe, or unknown")
        if normalized.get("evidence") not in EVIDENCE_STRENGTHS:
            raise CurationError("evidence must be strong, moderate, limited, or unknown")
        _required_text(normalized, "description")
    elif rule_type == "food_rule":
        normalized["medication"] = _required_text(normalized, "medication", 200).lower()
        if normalized.get("requirement") not in FOOD_REQUIREMENTS:
            raise CurationError("requirement must be with_food, empty_stomach, or no_restriction")
        _required_text(normalized, "note")
    elif rule_type == "drug_food_interaction":
        normalized["medication"] = _required_text(normalized, "medication", 200).lower()
        normalized["food_or_component"] = _required_text(normalized, "food_or_component", 200).lower()
        _required_text(normalized, "clinical_effect")
        if normalized.get("severity") not in SEVERITIES:
            raise CurationError("severity must be mild, moderate, severe, or unknown")
        if normalized.get("evidence_strength") not in EVIDENCE_STRENGTHS:
            raise CurationError("evidence_strength must be strong, moderate, limited, or unknown")
    elif rule_type == "contraindication":
        normalized["medication"] = _required_text(normalized, "medication", 200).lower()
        normalized["condition_or_population"] = _required_text(normalized, "condition_or_population", 300)
        _required_text(normalized, "clinical_action")
        if normalized.get("evidence_strength") not in EVIDENCE_STRENGTHS:
            raise CurationError("evidence_strength must be strong, moderate, limited, or unknown")
    elif rule_type == "dosage_reference":
        normalized["medication"] = _required_text(normalized, "medication", 200).lower()
        normalized["indication"] = _required_text(normalized, "indication", 500)
        normalized["population"] = _required_text(normalized, "population", 300)
        normalized["dose_text"] = _required_text(normalized, "dose_text", 1000)
        normalized["route"] = _required_text(normalized, "route", 100)
        normalized["frequency"] = _required_text(normalized, "frequency", 300)
        if normalized.get("evidence_strength") not in EVIDENCE_STRENGTHS:
            raise CurationError("evidence_strength must be strong, moderate, limited, or unknown")
        normalized["patient_specific"] = False
    elif rule_type == "administration_instruction":
        normalized["medication"] = _required_text(normalized, "medication", 200).lower()
        _required_text(normalized, "instruction", 2000)
        if normalized.get("evidence_strength") not in EVIDENCE_STRENGTHS:
            raise CurationError("evidence_strength must be strong, moderate, limited, or unknown")
    else:
        raise CurationError(f"unsupported candidate_type: {rule_type!r}")
    normalized["source"] = _required_text(normalized, "source", 1000)
    # Preserve evidence appraisal separately from clinical severity. Unknown is
    # explicit and never silently upgraded based on source identity.
    normalized["evidence_strength"] = normalized.get("evidence_strength", normalized.get("evidence", "unknown"))
    if normalized["evidence_strength"] not in EVIDENCE_STRENGTHS:
        raise CurationError("evidence_strength must be strong, moderate, limited, or unknown")
    normalized["source_quality_tier"] = normalized.get("source_quality_tier", "not_assessed")
    if normalized["source_quality_tier"] not in {"high", "moderate", "low", "not_assessed"}:
        raise CurationError("source_quality_tier is not recognized")
    normalized["applicability_notes"] = str(normalized.get("applicability_notes", "")).strip()[:2000]
    normalized["conflict_status"] = normalized.get("conflict_status", "not_assessed")
    if normalized["conflict_status"] not in {"not_assessed", "no_known_conflict", "conflicting_evidence", "resolved"}:
        raise CurationError("conflict_status is not recognized")
    normalized["conflict_resolution"] = str(normalized.get("conflict_resolution", "")).strip()[:2000]
    if normalized["conflict_status"] == "resolved" and not normalized["conflict_resolution"]:
        raise CurationError("conflict_resolution is required when conflict_status is resolved")
    normalized["source_quality_rationale"] = str(normalized.get("source_quality_rationale", "")).strip()[:2000]
    if normalized["source_quality_tier"] != "not_assessed" and not normalized["source_quality_rationale"]:
        raise CurationError("source_quality_rationale is required when source_quality_tier is assessed")
    normalized["evidence_direction"] = normalized.get("evidence_direction", "unknown")
    if normalized["evidence_direction"] not in {"supports", "contradicts", "qualifies", "unknown"}:
        raise CurationError("evidence_direction must be supports, contradicts, qualifies, or unknown")
    jurisdiction = normalized.get("jurisdiction", "unspecified")
    if not isinstance(jurisdiction, str) or not jurisdiction.strip() or len(jurisdiction) > 100:
        raise CurationError("jurisdiction must be a non-empty string of at most 100 characters")
    normalized["jurisdiction"] = jurisdiction.strip()
    # Rule IDs are assigned by the curation service, never supplied by an LLM/source.
    # Identifiers and publication metadata are server-assigned. Do not let a
    # candidate author spoof release IDs, approval state, or promotion state.
    for controlled_field in ("rule_id", "assertion_id", "candidate_id", "review_status",
                             "evidence_source_ids", "promotion_status", "candidate_status", "schema_version"):
        normalized.pop(controlled_field, None)
    return normalized


def _accepted_evidence(record_id: str, staging_root: Path) -> dict[str, Any]:
    accepted = {item["record_id"]: item for item in list_review_queue(staging_root, "accepted_for_curation")}
    if record_id not in accepted:
        raise CurationError(f"Evidence {record_id} is not currently accepted_for_curation")
    try:
        inspected = inspect_evidence(record_id, staging_root)
    except EvidenceReviewError as exc:
        raise CurationError(f"Evidence integrity verification failed: {exc}") from exc
    latest = inspected["record"].get("latest_decision") or {}
    if latest.get("source_response_sha256") != inspected["source_response_sha256"]:
        raise CurationError("Evidence review decision does not match the verified source hash")
    if latest.get("normalized_payload_sha256") != inspected["normalized_payload_sha256"]:
        raise CurationError("Evidence review decision does not match the verified normalized-payload hash")
    if inspected.get("metadata_integrity") != "verified":
        raise CurationError("Evidence metadata is not hash-bound to its accepted review; re-ingest and re-review this legacy record")
    if latest.get("metadata_sha256") != inspected.get("metadata_sha256"):
        raise CurationError("Evidence review decision does not match the verified metadata hash")
    return {
        "record_id": record_id,
        "source_id": inspected["record"].get("source_id"),
        "metadata_sha256": inspected["metadata_sha256"],
        "source_response_sha256": inspected["source_response_sha256"],
        "normalized_payload_sha256": inspected["normalized_payload_sha256"],
        "review_decision_id": latest.get("decision_id"),
        "reviewer_id": latest.get("reviewer_id"),
        "reviewed_at": latest.get("reviewed_at"),
    }


def create_candidate(
    candidate_type: str,
    rule: dict[str, Any],
    evidence_record_ids: list[str],
    author_id: str,
    rationale: str,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    curation_root: Path = DEFAULT_CURATION_ROOT,
) -> dict[str, Any]:
    """Create a human-authored candidate backed only by accepted, hash-verified evidence."""
    if candidate_type not in CANDIDATE_TYPES:
        raise CurationError("candidate_type must be interaction_rule or food_rule")
    author = _required_text({"author_id": author_id}, "author_id", 200)
    reason = _required_text({"rationale": rationale}, "rationale", 4000)
    if not isinstance(evidence_record_ids, list) or not evidence_record_ids:
        raise CurationError("at least one accepted evidence_record_id is required")
    if any(not isinstance(item, str) or not item.strip() for item in evidence_record_ids):
        raise CurationError("evidence_record_ids must contain non-empty strings")
    if len(set(evidence_record_ids)) != len(evidence_record_ids):
        raise CurationError("duplicate evidence_record_ids are not allowed")

    validated_rule = _validate_rule(candidate_type, rule)
    evidence = [_accepted_evidence(item, Path(staging_root)) for item in evidence_record_ids]
    candidate_id = "KNC-" + uuid.uuid4().hex[:16].upper()
    entry = {
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "candidate_type": candidate_type,
        "rule": validated_rule,
        "evidence": evidence,
        "author_id": author,
        "authored_at": _now(),
        "rationale": reason,
        "candidate_status": "pending_clinical_approval",
        "promotion_status": "not_promoted",
    }
    _append_jsonl(Path(curation_root) / CANDIDATE_FILE, entry)
    return entry


def list_candidates(curation_root: Path = DEFAULT_CURATION_ROOT) -> list[dict[str, Any]]:
    candidates = _read_jsonl(Path(curation_root) / CANDIDATE_FILE)
    decisions = _read_jsonl(Path(curation_root) / DECISION_FILE)
    latest: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        latest[decision.get("candidate_id", "")] = decision
    result = []
    for candidate in candidates:
        item = dict(candidate)
        decision = latest.get(candidate.get("candidate_id", ""))
        item["latest_clinical_decision"] = decision
        item["candidate_status"] = decision["decision"] if decision else "pending_clinical_approval"
        item["promotion_status"] = "not_promoted"
        result.append(item)
    return result


def record_clinical_decision(
    candidate_id: str,
    decision: str,
    reviewer_id: str,
    reviewer_role: str,
    rationale: str,
    curation_root: Path = DEFAULT_CURATION_ROOT,
    staging_root: Path = DEFAULT_STAGING_ROOT,
) -> dict[str, Any]:
    """Append an independent clinical approval/rejection; approval is not promotion."""
    if decision not in {"approved", "rejected", "request_changes"}:
        raise CurationError("decision must be approved, rejected, or request_changes")
    reviewer = _required_text({"reviewer_id": reviewer_id}, "reviewer_id", 200)
    reason = _required_text({"rationale": rationale}, "rationale", 4000)
    if reviewer_role not in CLINICAL_APPROVER_ROLES:
        raise CurationError("reviewer_role must be clinical_pharmacist or physician")
    candidates = {item["candidate_id"]: item for item in _read_jsonl(Path(curation_root) / CANDIDATE_FILE)}
    if candidate_id not in candidates:
        raise CurationError(f"candidate not found: {candidate_id}")
    candidate = candidates[candidate_id]
    # Re-check evidence at decision time: a later evidence-review decision or
    # changed source artifact must invalidate the candidate's approval path.
    current_evidence = [
        _accepted_evidence(item.get("record_id", ""), Path(staging_root))
        for item in candidate.get("evidence", [])
    ]
    if current_evidence != candidate.get("evidence"):
        raise CurationError("candidate evidence references no longer match the verified accepted evidence")
    if reviewer == candidate.get("author_id"):
        raise CurationError("candidate author cannot clinically approve or reject their own candidate")
    if decision == "approved" and candidate.get("candidate_type") in {
        "drug_food_interaction", "contraindication", "dosage_reference", "administration_instruction"
    } and candidate.get("rule", {}).get("conflict_status") not in {"no_known_conflict", "resolved"}:
        raise CurationError("Task 07 assertions require an explicit conflict assessment before clinical approval")
    previous = [d for d in _read_jsonl(Path(curation_root) / DECISION_FILE) if d.get("candidate_id") == candidate_id]
    if previous and previous[-1].get("decision") == "approved":
        raise CurationError("candidate is already clinically approved; create a new candidate revision to change it")
    entry = {
        "schema_version": "1.0.0",
        "decision_id": "KND-" + uuid.uuid4().hex[:16].upper(),
        "candidate_id": candidate_id,
        "decision": decision,
        "reviewer_id": reviewer,
        "reviewer_role": reviewer_role,
        "reviewed_at": _now(),
        "rationale": reason,
        "candidate_sha256": hashlib.sha256(
            json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest(),
        "promotion_status": "not_promoted",
    }
    _append_jsonl(Path(curation_root) / DECISION_FILE, entry)
    return entry
