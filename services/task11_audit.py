"""Task 11 release-governance acceptance audit.

The audit verifies software governance artifacts and runtime fail-closed
behavior. It does not authenticate reviewers or establish clinical correctness.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.knowledge_release import (
    DEFAULT_KNOWLEDGE_ROOT,
    ACTIVE_POINTER,
    RELEASE_REVIEW_LOG,
    KnowledgeReleaseError,
    _verified_release_review_events,
    list_releases,
    load_active_release,
    release_review_status,
)

POLICY_FILE = "release_governance_policy.json"


def _load_policy(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("release governance policy must not be a symbolic link")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read release governance policy: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("release governance policy must be a JSON object")
    return value


def _validate_policy(policy: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if policy.get("schema_version") != "1.0.0" or policy.get("policy_id") != "rxlogic-release-governance-v1":
        errors.append("policy identity or schema version is invalid")
    expected = {
        "clinical_release": {"clinical_pharmacist", "physician"},
        "governance_release": {"administrator", "knowledge_steward"},
    }
    requirements = policy.get("review_requirements")
    if not isinstance(requirements, list):
        errors.append("review_requirements must be a list")
    else:
        found = {}
        for row in requirements:
            if not isinstance(row, dict):
                errors.append("review requirement must be an object")
                continue
            kind = row.get("review_type")
            found[kind] = row
        if set(found) != set(expected):
            errors.append("policy must define clinical_release and governance_release reviews")
        for kind, roles in expected.items():
            row = found.get(kind, {})
            if set(row.get("allowed_roles", [])) != roles or row.get("minimum_approvals") != 1:
                errors.append(f"{kind} policy does not match the required approval roles/quorum")
    separation = policy.get("separation_of_duties")
    required_separation = {
        "release_reviewers_differ_from_release_creator",
        "release_reviewers_differ_from_candidate_authors",
        "release_reviewers_differ_from_candidate_clinical_approvers",
        "clinical_and_governance_reviewers_are_distinct",
        "promoter_differs_from_creator_and_all_reviewers",
    }
    if not isinstance(separation, dict) or any(separation.get(key) is not True for key in required_separation):
        errors.append("separation-of-duties policy is incomplete")
    if policy.get("rollback_requires_rationale") is not True:
        errors.append("rollback rationale requirement is missing")
    boundary = policy.get("identity_and_security_boundary")
    if not isinstance(boundary, dict) or boundary.get("local_cli_authenticates_reviewer_identity") is not False or boundary.get("hash_chain_is_digital_signature") is not False:
        errors.append("identity/security limitations must be explicit")
    if policy.get("clinical_use_permitted") is not False:
        errors.append("policy must keep clinical use disabled")
    return errors


def audit_task11(knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT) -> dict[str, Any]:
    root = Path(knowledge_root)
    checks: dict[str, bool] = {}
    errors: list[str] = []
    release_inventory: list[dict[str, Any]] = []
    review_event_count = 0
    active_status = "no_active_release"
    active_release_id = None
    policy_clinical_use_disabled = False
    active_clinical_use_disabled = True

    try:
        policy = _load_policy(root / POLICY_FILE)
        policy_errors = _validate_policy(policy)
        policy_clinical_use_disabled = policy.get("clinical_use_permitted") is False
        checks["versioned_dual_control_policy_valid"] = not policy_errors
        errors.extend(policy_errors)
    except ValueError as exc:
        checks["versioned_dual_control_policy_valid"] = False
        errors.append(str(exc))

    try:
        events = _verified_release_review_events(root / RELEASE_REVIEW_LOG)
        review_event_count = len(events)
        checks["release_review_log_hash_chain_valid"] = True
    except KnowledgeReleaseError as exc:
        checks["release_review_log_hash_chain_valid"] = False
        errors.append(str(exc))
        events = []

    try:
        release_inventory = list_releases(root)
        invalid = [item for item in release_inventory if item.get("integrity") != "valid"]
        checks["all_release_manifests_and_datasets_valid"] = not invalid
        if invalid:
            errors.append(f"{len(invalid)} release bundle(s) failed integrity validation")
        for item in release_inventory:
            manifest = item.get("manifest", {})
            if manifest.get("task11_schema_version") == "1.0.0":
                try:
                    status = release_review_status(item["release_id"], root)
                    item["governance_review_status"] = status["status"]
                except KnowledgeReleaseError as exc:
                    item["governance_review_status"] = "invalid"
                    errors.append(f"release {item['release_id']} governance review invalid: {exc}")
            else:
                item["governance_review_status"] = "requires_task11_rebuild"
        checks["release_review_states_are_verifiable"] = not any(
            item.get("governance_review_status") == "invalid" for item in release_inventory
        )
    except KnowledgeReleaseError as exc:
        checks["all_release_manifests_and_datasets_valid"] = False
        checks["release_review_states_are_verifiable"] = False
        errors.append(str(exc))

    if (root / ACTIVE_POINTER).exists():
        try:
            bundle = load_active_release(root)
            active_release_id = bundle["manifest"]["knowledge_release"]
            active_status = "active_and_verified"
            checks["active_release_has_current_dual_approval"] = True
            checks["runtime_active_release_loads_fail_closed_integrity_checks"] = True
            active_clinical_use_disabled = bundle["manifest"].get("publication_policy", {}).get("clinical_use_permitted") is False
            if not active_clinical_use_disabled:
                errors.append("active release does not explicitly prohibit clinical use")
        except KnowledgeReleaseError as exc:
            active_status = "invalid_active_pointer_rejected"
            checks["active_release_has_current_dual_approval"] = False
            checks["runtime_active_release_loads_fail_closed_integrity_checks"] = False
            errors.append(f"active release rejected: {exc}")
    else:
        try:
            load_active_release(root)
        except KnowledgeReleaseError as exc:
            active_status = "no_active_release_fail_closed"
            checks["active_release_has_current_dual_approval"] = True
            checks["runtime_active_release_loads_fail_closed_integrity_checks"] = (
                "no active approved knowledge release" in str(exc)
            )
        else:
            checks["active_release_has_current_dual_approval"] = False
            checks["runtime_active_release_loads_fail_closed_integrity_checks"] = False
            errors.append("runtime unexpectedly loaded without an active release pointer")

    checks["active_pointer_absent_or_active_release_has_current_dual_approval"] = checks.get("active_release_has_current_dual_approval", False)
    checks["clinical_use_remains_disabled"] = policy_clinical_use_disabled and active_clinical_use_disabled
    passed = all(checks.values()) and not errors
    return {
        "schema_version": "1.0.0",
        "audit_type": "task11_release_governance_and_dual_control_audit",
        "passed": passed,
        "checks": checks,
        "release_count": len(release_inventory),
        "release_review_event_count": review_event_count,
        "active_release_status": active_status,
        "active_release_id": active_release_id,
        "releases": release_inventory,
        "errors": errors,
        "limitations": [
            "CLI reviewer IDs and role strings are audit declarations, not authenticated identities or verified professional credentials.",
            "The local SHA-256 hash chain is tamper-evident, not a digital signature or external trust anchor.",
            "The audit verifies release governance and runtime integrity, not clinical correctness or comprehensive evidence coverage.",
            "Clinical use remains prohibited; independent clinical validation and separate deployment authorization are not established.",
            "Concurrent release mutations must be serialized by deployment operations; JSONL storage is not a multi-host transaction system."
        ],
    }
