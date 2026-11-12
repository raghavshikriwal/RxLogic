"""Immutable, explicitly promoted knowledge releases (Task 06, Stage 2).

A release contains only independently approved candidates. Creating a release
never activates it; promotion is a separate, audited operation. Runtime readers
must call ``load_active_release`` and never fall back to development datasets.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.evidence_review import DEFAULT_STAGING_ROOT, EvidenceReviewError, inspect_evidence
from services.knowledge_curation import (
    CurationError, DEFAULT_CURATION_ROOT, _accepted_evidence, _read_jsonl,
)
from services.clinical_knowledge import validate_clinical_assertions, validate_release_evidence_sources

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge"
RELEASES_DIR = "releases"
ACTIVE_POINTER = "active_release.json"
PROMOTION_LOG = "promotion_events.jsonl"
PROMOTER_ROLES = frozenset({"knowledge_steward", "administrator"})


class KnowledgeReleaseError(ValueError):
    """Raised when release creation, promotion, loading, or rollback is unsafe."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise KnowledgeReleaseError(f"{path} must not be a symbolic link")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KnowledgeReleaseError(f"Cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise KnowledgeReleaseError(f"{path} must contain a JSON object")
    return value


def _event_digest(event: dict[str, Any]) -> str:
    payload = {key: value for key, value in event.items() if key != "event_sha256"}
    return _canonical_hash(payload)


def _verified_promotion_events(path: Path) -> list[dict[str, Any]]:
    """Read the append-only audit log and verify its tamper-evident hash chain."""
    if not path.exists():
        return []
    if path.is_symlink():
        raise KnowledgeReleaseError("promotion event log must not be a symbolic link")
    events: list[dict[str, Any]] = []
    previous = "0" * 64
    try:
        with path.open("r", encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError(f"line {number} is not an object")
                if event.get("previous_event_sha256") != previous:
                    raise ValueError(f"line {number} has an invalid previous-event hash")
                digest = event.get("event_sha256")
                if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                    raise ValueError(f"line {number} has no valid event hash")
                if _event_digest(event) != digest:
                    raise ValueError(f"line {number} event hash does not match its content")
                if event.get("event") not in {"promote", "rollback", "promote_committed", "rollback_committed"}:
                    raise ValueError(f"line {number} has an unknown event type")
                previous = digest
                events.append(event)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise KnowledgeReleaseError(f"promotion audit log integrity check failed: {exc}") from exc
    return events


def _append_event(path: Path, event: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise KnowledgeReleaseError("promotion event log must not be a symbolic link")
    history = _verified_promotion_events(path)
    chained = dict(event)
    chained["previous_event_sha256"] = history[-1]["event_sha256"] if history else "0" * 64
    chained["event_sha256"] = _event_digest(chained)
    data = (json.dumps(chained, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "ab") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return chained


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise KnowledgeReleaseError(f"{path.name} must not be a symbolic link")
    temp = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _candidate_and_approval(candidate_id: str, curation_root: Path, staging_root: Path) -> tuple[dict, dict]:
    candidates = {row.get("candidate_id"): row for row in _read_jsonl(curation_root / "candidates.jsonl")}
    if candidate_id not in candidates:
        raise KnowledgeReleaseError(f"candidate not found: {candidate_id}")
    decisions = [row for row in _read_jsonl(curation_root / "candidate_decisions.jsonl") if row.get("candidate_id") == candidate_id]
    if not decisions or decisions[-1].get("decision") != "approved":
        raise KnowledgeReleaseError(f"candidate {candidate_id} does not have a current clinical approval")
    candidate, approval = candidates[candidate_id], decisions[-1]
    if approval.get("reviewer_role") not in {"clinical_pharmacist", "physician"}:
        raise KnowledgeReleaseError("clinical approval role is not authorized")
    if approval.get("reviewer_id") == candidate.get("author_id"):
        raise KnowledgeReleaseError("candidate author cannot approve their own candidate")
    if approval.get("candidate_sha256") != _canonical_hash(candidate):
        raise KnowledgeReleaseError("candidate content no longer matches its clinical approval")
    try:
        current = [_accepted_evidence(item.get("record_id", ""), staging_root) for item in candidate.get("evidence", [])]
    except CurationError as exc:
        raise KnowledgeReleaseError(f"candidate evidence is no longer eligible: {exc}") from exc
    if not current or current != candidate.get("evidence"):
        raise KnowledgeReleaseError("candidate evidence no longer matches verified accepted evidence")
    return candidate, approval


def create_release(
    candidate_ids: list[str], author_id: str, rationale: str,
    curation_root: Path = DEFAULT_CURATION_ROOT,
    staging_root: Path = DEFAULT_STAGING_ROOT,
    knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
) -> dict[str, Any]:
    """Build an immutable release from approved candidates; does not activate it."""
    if not isinstance(candidate_ids, list) or not candidate_ids or len(set(candidate_ids)) != len(candidate_ids):
        raise KnowledgeReleaseError("candidate_ids must be a non-empty list without duplicates")
    if not isinstance(author_id, str) or not author_id.strip() or len(author_id.strip()) > 200:
        raise KnowledgeReleaseError("author_id is required")
    if not isinstance(rationale, str) or not rationale.strip() or len(rationale.strip()) > 4000:
        raise KnowledgeReleaseError("rationale is required and must be at most 4000 characters")

    selected = [_candidate_and_approval(cid, Path(curation_root), Path(staging_root)) for cid in candidate_ids]
    interactions: list[dict] = []
    foods: list[dict] = []
    clinical_assertions: dict[str, list[dict]] = {
        "drug_food_interactions": [],
        "contraindications": [],
        "dosage_references": [],
        "administration_instructions": [],
    }
    seen: set[tuple] = set()
    evidence_sources: dict[str, dict] = {}
    for candidate, approval in selected:
        rule = dict(candidate["rule"])
        rule_id = f"{candidate['candidate_type'].upper()}-{candidate['candidate_id']}"
        evidence_ids = [item.get("source_id") for item in candidate["evidence"] if item.get("source_id")]
        rule.update({"rule_id": rule_id, "evidence_source_ids": sorted(set(evidence_ids)), "review_status": "clinically_approved"})
        if candidate["candidate_type"] in {"drug_food_interaction", "contraindication", "dosage_reference", "administration_instruction"}:
            rule["assertion_id"] = rule_id
        rule["jurisdiction"] = rule.get("jurisdiction", "unspecified")
        if candidate["candidate_type"] == "interaction_rule":
            key = tuple(sorted((rule["medication_a"], rule["medication_b"])))
            if key in seen:
                raise KnowledgeReleaseError(f"duplicate interaction pair in release: {key}")
            seen.add(key)
            interactions.append(rule)
        elif candidate["candidate_type"] == "food_rule":
            key = ("food_rule", rule["medication"])
            if key in seen:
                raise KnowledgeReleaseError(f"duplicate food rule in release: {key}")
            seen.add(key)
            foods.append(rule)
        elif candidate["candidate_type"] in {"drug_food_interaction", "contraindication", "dosage_reference", "administration_instruction"}:
            domain = {
                "drug_food_interaction": "drug_food_interactions",
                "contraindication": "contraindications",
                "dosage_reference": "dosage_references",
                "administration_instruction": "administration_instructions",
            }[candidate["candidate_type"]]
            identity_fields = {
                "drug_food_interaction": ("medication", "food_or_component"),
                "contraindication": ("medication", "condition_or_population"),
                "dosage_reference": ("medication", "indication", "population", "route"),
                "administration_instruction": ("medication", "instruction"),
            }[candidate["candidate_type"]]
            key = (candidate["candidate_type"],) + tuple(str(rule.get(field, "")).casefold() for field in identity_fields)
            if key in seen:
                raise KnowledgeReleaseError(f"duplicate {candidate['candidate_type']} assertion in release: {key}")
            seen.add(key)
            legacy_medications = _read_json(Path(knowledge_root) / "interaction_rules.json").get("medications", {})
            if str(rule.get("medication", "")).casefold() not in {str(name).casefold() for name in legacy_medications}:
                raise KnowledgeReleaseError(f"candidate references unknown medication: {rule.get('medication')!r}")
            clinical_assertions[domain].append(rule)
        else:
            raise KnowledgeReleaseError("unsupported candidate type in approved candidate")
        for evidence in candidate["evidence"]:
            try:
                inspected = inspect_evidence(evidence["record_id"], Path(staging_root))
            except EvidenceReviewError as exc:
                raise KnowledgeReleaseError(f"cannot inspect evidence {evidence['record_id']}: {exc}") from exc
            source_id = evidence.get("source_id")
            if source_id:
                source_record = evidence_sources.setdefault(source_id, {
                    "source_id": source_id,
                    "publisher": inspected["metadata"].get("publisher", "unknown"),
                    "source_type": inspected["metadata"].get("source_type", "unknown"),
                    "document_title": inspected["metadata"].get("document_title"),
                    "publication_date": inspected["metadata"].get("publication_date"),
                    "canonical_url": inspected["metadata"].get("canonical_url"),
                    "jurisdiction": inspected["metadata"].get("jurisdiction"),
                    "retrieved_at": inspected.get("retrieved_at"),
                    "verification_status": "integrity_verified_clinical_review_recorded",
                    "source_response_sha256": evidence["source_response_sha256"],
                    "normalized_payload_sha256": evidence["normalized_payload_sha256"],
                    "metadata_sha256": evidence["metadata_sha256"],
                    "source_quality_assessments": [],
                })
                appraisal = {
                    "candidate_id": candidate["candidate_id"],
                    "quality": candidate.get("rule", {}).get("source_quality_tier", "not_assessed"),
                    "rationale": candidate.get("rule", {}).get("source_quality_rationale", ""),
                    "evidence_direction": candidate.get("rule", {}).get("evidence_direction", "unknown"),
                    "clinical_decision_id": approval.get("decision_id"),
                    "clinical_reviewer_id": approval.get("reviewer_id"),
                    "clinical_reviewer_role": approval.get("reviewer_role"),
                    "clinical_reviewed_at": approval.get("reviewed_at"),
                }
                if appraisal not in source_record["source_quality_assessments"]:
                    source_record["source_quality_assessments"].append(appraisal)

    # Preserve terminology coverage only; do not copy legacy, unreviewed rules.
    legacy = _read_json(Path(knowledge_root) / "interaction_rules.json")
    release_id = "RXK-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8].upper()
    created_at = _now()
    datasets = {
        "interaction_rules.json": {"schema_version": "2.0.0", "knowledge_release": release_id,
                                   "source_note": "Only independently clinically approved candidates are included.",
                                   "medications": legacy.get("medications", {}), "interaction_rules": interactions},
        "food_rules.json": {"schema_version": "2.0.0", "knowledge_release": release_id,
                             "source_note": "Only independently clinically approved candidates are included.", "food_rules": foods},
        "evidence_sources.json": {"schema_version": "1.0.0", "sources": list(evidence_sources.values())},
        "clinical_assertions.json": {"schema_version": "1.0.0", "knowledge_release": release_id, **clinical_assertions},
    }
    hashes = {name: _canonical_hash(content) for name, content in datasets.items()}
    manifest = {
        "schema_version": "1.0.0", "task07_schema_version": "1.0.0",
        "knowledge_release": release_id, "release_status": "immutable_release",
        "created_at": created_at, "created_by": author_id.strip(), "rationale": rationale.strip(),
        "candidate_ids": candidate_ids, "clinical_approval_ids": [approval["decision_id"] for _, approval in selected],
        "datasets": {name: {"sha256": digest} for name, digest in hashes.items()},
        "publication_policy": {"runtime_may_load_unreviewed_records": False, "clinical_use_permitted": False,
                               "note": "Governance release; not clinical validation or authorization for patient-care use."},
    }
    release_root = Path(knowledge_root) / RELEASES_DIR
    release_root.mkdir(parents=True, exist_ok=True)
    target = release_root / release_id
    if target.exists():
        raise KnowledgeReleaseError("release ID collision; retry release creation")
    temp = release_root / (".tmp-" + release_id)
    temp.mkdir()
    try:
        for name, content in datasets.items():
            (temp / name).write_text(json.dumps(content, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        (temp / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        # Atomic directory rename makes the completed release visible as one unit.
        os.replace(temp, target)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return manifest


def _validate_release(release_dir: Path) -> dict[str, Any]:
    manifest = _read_json(release_dir / "manifest.json")
    release_id = manifest.get("knowledge_release")
    if not isinstance(release_id, str) or release_dir.name != release_id:
        raise KnowledgeReleaseError("release directory and manifest ID do not match")
    if manifest.get("release_status") not in {"immutable_release"}:
        raise KnowledgeReleaseError("release has an invalid status")
    legacy_datasets = {"interaction_rules.json", "food_rules.json", "evidence_sources.json"}
    task07_datasets = legacy_datasets | {"clinical_assertions.json"}
    datasets = manifest.get("datasets")
    task07_version = manifest.get("task07_schema_version")
    if task07_version == "1.0.0":
        required_datasets = task07_datasets
    elif task07_version is None:
        # Backward-compatible read support for immutable Task 06 releases.
        required_datasets = legacy_datasets
    else:
        raise KnowledgeReleaseError("release has an unsupported Task 07 schema version")
    if not isinstance(datasets, dict) or set(datasets) != required_datasets:
        raise KnowledgeReleaseError("release manifest must declare exactly the required datasets")
    for name in sorted(required_datasets):
        info = datasets[name]
        if not isinstance(info, dict) or not re.fullmatch(r"[a-f0-9]{64}", str(info.get("sha256", ""))):
            raise KnowledgeReleaseError(f"release manifest has an invalid dataset hash: {name}")
        data = _read_json(release_dir / name)
        if _canonical_hash(data) != info["sha256"]:
            raise KnowledgeReleaseError(f"release dataset integrity check failed: {name}")
    if task07_version == "1.0.0":
        clinical = _read_json(release_dir / "clinical_assertions.json")
        interaction_data = _read_json(release_dir / "interaction_rules.json")
        evidence_data = _read_json(release_dir / "evidence_sources.json")
        if clinical.get("knowledge_release") != release_id:
            raise KnowledgeReleaseError("clinical assertion dataset release ID does not match manifest")
        source_errors = validate_release_evidence_sources(evidence_data)
        if source_errors:
            raise KnowledgeReleaseError("release evidence-source dataset is invalid: " + "; ".join(source_errors))
        clinical_errors = validate_clinical_assertions(
            clinical,
            {str(name).casefold() for name in interaction_data.get("medications", {})},
            {str(item.get("source_id")) for item in evidence_data.get("sources", []) if item.get("source_id")},
        )
        if clinical_errors:
            raise KnowledgeReleaseError("clinical assertion dataset is invalid: " + "; ".join(clinical_errors))
    policy = manifest.get("publication_policy")
    if not isinstance(policy, dict) or policy.get("runtime_may_load_unreviewed_records") is not False or policy.get("clinical_use_permitted") is not False:
        raise KnowledgeReleaseError("release publication policy is missing or unsafe")
    return manifest


def promote_release(
    release_id: str, actor_id: str, actor_role: str,
    knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
    curation_root: Path = DEFAULT_CURATION_ROOT,
    staging_root: Path = DEFAULT_STAGING_ROOT,
) -> dict[str, Any]:
    """Explicitly activate a built release; only knowledge stewards/admins may do so."""
    if actor_role not in PROMOTER_ROLES:
        raise KnowledgeReleaseError("actor_role must be knowledge_steward or administrator")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise KnowledgeReleaseError("actor_id is required")
    if not re.fullmatch(r"RXK-\d{8}T\d{6}Z-[A-F0-9]{8}", release_id):
        raise KnowledgeReleaseError("invalid release ID")
    root = Path(knowledge_root)
    release_dir = root / RELEASES_DIR / release_id
    if not release_dir.is_dir() or release_dir.is_symlink():
        raise KnowledgeReleaseError("release does not exist or is not a safe directory")
    manifest = _validate_release(release_dir)
    if manifest["release_status"] != "immutable_release":
        raise KnowledgeReleaseError("only an immutable, inactive release can be promoted")
    # Approval and evidence are revalidated at activation time, not only when
    # the release bundle was assembled. This closes the build-to-promote gap.
    current_approvals = []
    for candidate_id in manifest.get("candidate_ids", []):
        _candidate, approval = _candidate_and_approval(candidate_id, Path(curation_root), Path(staging_root))
        current_approvals.append(approval.get("decision_id"))
    if current_approvals != manifest.get("clinical_approval_ids"):
        raise KnowledgeReleaseError("release clinical approvals changed after release assembly")
    pointer_path = root / ACTIVE_POINTER
    previous = _read_json(pointer_path).get("knowledge_release") if pointer_path.exists() else None
    manifest_sha256 = hashlib.sha256((release_dir / "manifest.json").read_bytes()).hexdigest()
    pointer = {"schema_version": "1.0.0", "knowledge_release": release_id, "manifest_sha256": manifest_sha256,
               "activated_at": _now(), "activated_by": actor_id.strip(), "actor_role": actor_role,
               "previous_release": previous}
    event = {"event_id": "KNP-" + uuid.uuid4().hex[:16].upper(), "event": "promote", **pointer}
    # Persist the audit event first; the pointer binds to its hash. A crash
    # between these writes leaves the old pointer valid and the new event
    # visible as an attempted activation, never an unaudited active release.
    intent_event = _append_event(root / PROMOTION_LOG, event)
    pointer["audit_event_sha256"] = intent_event["event_sha256"]
    _atomic_json(pointer_path, pointer)
    return _append_event(root / PROMOTION_LOG, {
        "event_id": "KNP-" + uuid.uuid4().hex[:16].upper(),
        "event": "promote_committed", "operation_event_sha256": intent_event["event_sha256"],
        "knowledge_release": release_id, "manifest_sha256": manifest_sha256,
        "activated_at": pointer["activated_at"], "activated_by": pointer["activated_by"],
        "actor_role": actor_role,
    })


def rollback_release(
    target_release_id: str, actor_id: str, actor_role: str,
    knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT,
) -> dict[str, Any]:
    """Point runtime back to an existing previously promoted release."""
    if actor_role not in PROMOTER_ROLES:
        raise KnowledgeReleaseError("actor_role must be knowledge_steward or administrator")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise KnowledgeReleaseError("actor_id is required")
    if not re.fullmatch(r"RXK-\d{8}T\d{6}Z-[A-F0-9]{8}", target_release_id):
        raise KnowledgeReleaseError("invalid rollback release ID")
    root = Path(knowledge_root)
    target = root / RELEASES_DIR / target_release_id
    if not target.is_dir() or target.is_symlink():
        raise KnowledgeReleaseError("rollback target is not an existing release")
    manifest = _validate_release(target)
    pointer_path = root / ACTIVE_POINTER
    if not pointer_path.exists():
        raise KnowledgeReleaseError("there is no active release to roll back from")
    current = _read_json(pointer_path).get("knowledge_release")
    if current == target_release_id:
        raise KnowledgeReleaseError("target release is already active")
    history = _verified_promotion_events(root / PROMOTION_LOG)
    committed_intents = {event.get("operation_event_sha256") for event in history if event.get("event") in {"promote_committed", "rollback_committed"}}
    promoted = {event.get("knowledge_release") for event in history if event.get("event") in {"promote", "rollback"} and event.get("event_sha256") in committed_intents}
    if target_release_id not in promoted:
        raise KnowledgeReleaseError("rollback target is not in promotion history")
    manifest_sha256 = hashlib.sha256((target / "manifest.json").read_bytes()).hexdigest()
    pointer = {"schema_version": "1.0.0", "knowledge_release": target_release_id,
               "manifest_sha256": manifest_sha256, "activated_at": _now(),
               "activated_by": actor_id.strip(), "actor_role": actor_role, "previous_release": current}
    event = {"event_id": "KNP-" + uuid.uuid4().hex[:16].upper(), "event": "rollback", **pointer}
    intent_event = _append_event(root / PROMOTION_LOG, event)
    pointer["audit_event_sha256"] = intent_event["event_sha256"]
    _atomic_json(pointer_path, pointer)
    return _append_event(root / PROMOTION_LOG, {
        "event_id": "KNP-" + uuid.uuid4().hex[:16].upper(),
        "event": "rollback_committed", "operation_event_sha256": intent_event["event_sha256"],
        "knowledge_release": target_release_id, "manifest_sha256": manifest_sha256,
        "activated_at": pointer["activated_at"], "activated_by": pointer["activated_by"],
        "actor_role": actor_role,
    })


def load_active_release(knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT) -> dict[str, Any]:
    """Fail-closed runtime loader: no active pointer means no approved rules."""
    root = Path(knowledge_root)
    pointer_path = root / ACTIVE_POINTER
    if not pointer_path.exists():
        raise KnowledgeReleaseError("no active approved knowledge release; refusing legacy/unreviewed fallback")
    pointer = _read_json(pointer_path)
    events = _verified_promotion_events(root / PROMOTION_LOG)
    pointer_event_hash = pointer.get("audit_event_sha256")
    matching_events = [event for event in events if event.get("event_sha256") == pointer_event_hash]
    if not matching_events:
        raise KnowledgeReleaseError("active release pointer is not bound to a verified promotion audit event")
    bound_event = matching_events[-1]
    committed = any(
        event.get("event") in {"promote_committed", "rollback_committed"}
        and event.get("operation_event_sha256") == pointer_event_hash
        and event.get("knowledge_release") == pointer.get("knowledge_release")
        and event.get("manifest_sha256") == pointer.get("manifest_sha256")
        for event in events
    )
    if not committed:
        raise KnowledgeReleaseError("active release pointer has no committed promotion audit event")
    if bound_event.get("knowledge_release") != pointer.get("knowledge_release") or bound_event.get("manifest_sha256") != pointer.get("manifest_sha256"):
        raise KnowledgeReleaseError("active release pointer does not match its promotion audit event")
    release_id = pointer.get("knowledge_release")
    if not isinstance(release_id, str) or not re.fullmatch(r"RXK-[A-Z0-9T-]+", release_id):
        raise KnowledgeReleaseError("active release pointer contains an invalid release ID")
    release_dir = root / RELEASES_DIR / release_id
    if not release_dir.is_dir() or release_dir.is_symlink():
        raise KnowledgeReleaseError("active release directory is missing or unsafe")
    manifest = _validate_release(release_dir)
    manifest_sha256 = hashlib.sha256((release_dir / "manifest.json").read_bytes()).hexdigest()
    if pointer.get("manifest_sha256") != manifest_sha256:
        raise KnowledgeReleaseError("active release manifest integrity check failed")
    if manifest.get("publication_policy", {}).get("runtime_may_load_unreviewed_records") is not False:
        raise KnowledgeReleaseError("active release policy permits unreviewed records")
    return {"pointer": pointer, "manifest": manifest,
            "interaction_rules": _read_json(release_dir / "interaction_rules.json"),
            "food_rules": _read_json(release_dir / "food_rules.json"),
            "evidence_sources": _read_json(release_dir / "evidence_sources.json"),
            "clinical_assertions": (
                _read_json(release_dir / "clinical_assertions.json")
                if (release_dir / "clinical_assertions.json").exists()
                else {"schema_version": "1.0.0", "knowledge_release": release_id,
                      "drug_food_interactions": [], "contraindications": [],
                      "dosage_references": [], "administration_instructions": []}
            )}


def inspect_release(release_id: str, knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT) -> dict[str, Any]:
    """Return a verified release manifest; never returns unverified datasets."""
    if not isinstance(release_id, str) or not re.fullmatch(r"RXK-\d{8}T\d{6}Z-[A-F0-9]{8}", release_id):
        raise KnowledgeReleaseError("invalid release ID")
    folder = Path(knowledge_root) / RELEASES_DIR / release_id
    if not folder.is_dir() or folder.is_symlink():
        raise KnowledgeReleaseError("release does not exist or is not a safe directory")
    return _validate_release(folder)


def list_releases(knowledge_root: Path = DEFAULT_KNOWLEDGE_ROOT) -> list[dict[str, Any]]:
    """List release bundles, explicitly marking any failed integrity check."""
    root = Path(knowledge_root) / RELEASES_DIR
    if not root.exists():
        return []
    if root.is_symlink() or not root.is_dir():
        raise KnowledgeReleaseError("release directory is missing or unsafe")
    result = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            continue
        try:
            manifest = _validate_release(folder)
            result.append({"release_id": folder.name, "integrity": "valid", "manifest": manifest})
        except KnowledgeReleaseError as exc:
            result.append({"release_id": folder.name, "integrity": "invalid", "error": str(exc)})
    return result
