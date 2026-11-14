from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
from services.evidence_review import record_review_decision
from services.knowledge_curation import create_candidate, record_clinical_decision
from services.knowledge_release import (
    KnowledgeReleaseError, create_release, load_active_release,
    promote_release, record_release_review, release_review_status, rollback_release,
)
from services.rule_engine import RuleEngine
from services.food_rules import FoodRules


@pytest.fixture()
def approved_candidate(tmp_path):
    source = tmp_path / "source.json"
    source.write_bytes(b'{"source":"synthetic clinical evidence"}\n')
    staging = tmp_path / "staging"
    evidence = ingest_json_document(source, EvidenceMetadata(
        publisher="Synthetic Publisher", source_type="other",
        document_title="Synthetic release test", canonical_url="https://api.fda.gov/test-evidence",
    ), staging)
    record_review_decision(evidence.record_id, "accepted_for_curation", "evidence-reviewer", "clinical_reviewer", "Accepted for test curation.", staging)
    curation = tmp_path / "curation"
    candidate = create_candidate(
        "interaction_rule",
        {"medication_a": "warfarin", "medication_b": "aspirin", "severity": "severe",
         "evidence": "moderate", "description": "Synthetic test only.", "source": "Synthetic source", "jurisdiction": "US"},
        [evidence.record_id], "candidate-author", "Synthetic test candidate.", staging, curation,
    )
    record_clinical_decision(candidate["candidate_id"], "approved", "independent-pharmacist", "clinical_pharmacist", "Synthetic approval for test only.", curation, staging)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    project_policy = Path(__file__).resolve().parent.parent / "knowledge" / "release_governance_policy.json"
    (knowledge / "release_governance_policy.json").write_bytes(project_policy.read_bytes())
    # Only medication terminology is copied into the generated release.
    (knowledge / "interaction_rules.json").write_text(json.dumps({"medications": {"warfarin": "11289", "aspirin": "1191"}, "interaction_rules": [{"rule_id": "UNREVIEWED", "medication_a": "warfarin", "medication_b": "aspirin", "severity": "severe", "description": "must not leak", "source": "legacy"}]}), encoding="utf-8")
    (knowledge / "medication_catalog.json").write_text(json.dumps({
        "schema_version": "1.0.0", "catalog_id": "test-catalog", "catalog_status": "development_identity_registry",
        "clinical_use_permitted": False,
        "identity_source": {"publisher": "NLM", "name": "RxNorm", "url": "https://www.nlm.nih.gov/research/umls/rxnorm/"},
        "medications": [
            {"canonical_name": "warfarin", "rxcui": "11289", "aliases": [], "identity_status": "existing_catalog_entry", "clinical_coverage_status": "legacy_assertions_unreviewed_partial"},
            {"canonical_name": "aspirin", "rxcui": "1191", "aliases": [], "identity_status": "existing_catalog_entry", "clinical_coverage_status": "legacy_assertions_unreviewed_partial"}
        ]
    }), encoding="utf-8")
    return candidate, curation, staging, knowledge


def approve_release_for_promotion(manifest, knowledge):
    """Synthetic two-person release review for software lifecycle tests only."""
    release_id = manifest["knowledge_release"]
    record_release_review(
        release_id, "release-clinical-reviewer", "clinical_pharmacist", "clinical_release",
        "approved", "Synthetic test-only release review.", knowledge,
    )
    record_release_review(
        release_id, "release-governance-reviewer", "knowledge_steward", "governance_release",
        "approved", "Synthetic test-only governance review.", knowledge,
    )


def promote_with_task11_reviews(manifest, curation, staging, knowledge):
    approve_release_for_promotion(manifest, knowledge)
    return promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward",
                           knowledge, curation, staging)


def test_release_build_includes_only_approved_candidates_and_does_not_activate(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    release = knowledge / "releases" / manifest["knowledge_release"]
    interaction = json.loads((release / "interaction_rules.json").read_text())
    assert len(interaction["interaction_rules"]) == 1
    assert interaction["interaction_rules"][0]["review_status"] == "clinically_approved"
    assert interaction["interaction_rules"][0]["rule_id"] != "UNREVIEWED"
    assert not (knowledge / "active_release.json").exists()
    with pytest.raises(KnowledgeReleaseError, match="no active approved"):
        load_active_release(knowledge)


def test_only_steward_can_promote_and_active_runtime_loads_release(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    with pytest.raises(KnowledgeReleaseError, match="knowledge_steward"):
        promote_release(manifest["knowledge_release"], "reviewer", "clinical_pharmacist", knowledge, curation, staging)
    approve_release_for_promotion(manifest, knowledge)
    promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    bundle = load_active_release(knowledge)
    assert bundle["manifest"]["knowledge_release"] == manifest["knowledge_release"]
    engine = RuleEngine.from_active_release(knowledge)
    food = FoodRules.from_active_release(knowledge)
    assert engine.knowledge_release == manifest["knowledge_release"]
    assert len(engine.rules) == 1
    assert food.rules == {}
    assert bundle["medication_catalog"]["catalog_id"] == "test-catalog"
    assert engine.medication_catalog["catalog_id"] == "test-catalog"


def test_release_tampering_is_detected_by_runtime_loader(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    path = knowledge / "releases" / manifest["knowledge_release"] / "interaction_rules.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["interaction_rules"][0]["description"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="integrity check failed"):
        load_active_release(knowledge)


def test_rollback_requires_previously_promoted_release_and_restores_it(approved_candidate, tmp_path):
    candidate, curation, staging, knowledge = approved_candidate
    first = create_release([candidate["candidate_id"]], "steward", "First release.", curation, staging, knowledge)
    promote_with_task11_reviews(first, curation, staging, knowledge)
    # Build a second release from the same approved candidate in a separate curation store.
    # A release cannot be re-promoted, so the second candidate is a distinct approved record.
    source = tmp_path / "second.json"
    source.write_bytes(b'{"source":"second synthetic evidence"}')
    evidence = ingest_json_document(source, EvidenceMetadata(publisher="Synthetic", source_type="other", document_title="Second", canonical_url="https://api.fda.gov/second"), staging)
    record_review_decision(evidence.record_id, "accepted_for_curation", "reviewer", "clinical_reviewer", "Accepted.", staging)
    second_candidate = create_candidate("food_rule", {"medication": "metformin", "requirement": "with_food", "note": "Synthetic only", "source": "Synthetic source"}, [evidence.record_id], "author-2", "Second test candidate", staging, curation)
    record_clinical_decision(second_candidate["candidate_id"], "approved", "doctor-2", "physician", "Synthetic approval", curation, staging)
    second = create_release([second_candidate["candidate_id"]], "steward", "Second release.", curation, staging, knowledge)
    promote_with_task11_reviews(second, curation, staging, knowledge)
    rollback_release(first["knowledge_release"], "independent-rollbacker", "administrator", knowledge,
                     "Synthetic test rollback after second release.", curation, staging)
    assert load_active_release(knowledge)["manifest"]["knowledge_release"] == first["knowledge_release"]


def test_unapproved_candidate_cannot_be_released(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    decisions = curation / "candidate_decisions.jsonl"
    decisions.write_text("", encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="current clinical approval"):
        create_release([candidate["candidate_id"]], "steward", "Must fail", curation, staging, knowledge)


def test_promotion_rechecks_evidence_after_release_assembly(approved_candidate):
    from services.evidence_review import record_review_decision

    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    record_review_decision(candidate["evidence"][0]["record_id"], "request_more_evidence", "reviewer-2", "clinical_reviewer", "Evidence re-review requested.", staging)
    with pytest.raises(KnowledgeReleaseError, match="no longer eligible"):
        promote_with_task11_reviews(manifest, curation, staging, knowledge)
    assert not (knowledge / "active_release.json").exists()


def test_active_manifest_tampering_is_detected(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    manifest_path = knowledge / "releases" / manifest["knowledge_release"] / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["candidate_ids"] = []
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="manifest integrity check failed"):
        load_active_release(knowledge)


def test_list_releases_reports_empty_directory(tmp_path):
    from services.knowledge_release import list_releases
    assert list_releases(tmp_path) == []


def test_inspect_release_rejects_invalid_id(tmp_path):
    from services.knowledge_release import KnowledgeReleaseError, inspect_release
    with pytest.raises(KnowledgeReleaseError, match="invalid release ID"):
        inspect_release("not-a-release", tmp_path)


def test_active_runtime_rejects_modified_promotion_audit_log(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    log = knowledge / "promotion_events.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["activated_by"] = "forged-actor"
    lines[0] = json.dumps(event)
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="audit log integrity check failed"):
        load_active_release(knowledge)


def test_active_runtime_rejects_pointer_not_bound_to_audit_event(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    pointer_path = knowledge / "active_release.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["audit_event_sha256"] = "0" * 64
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="not bound to a verified promotion audit event"):
        load_active_release(knowledge)


def test_release_manifest_must_declare_exact_dataset_set(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    manifest_path = knowledge / "releases" / manifest["knowledge_release"] / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["datasets"].pop("evidence_sources.json")
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    from services.knowledge_release import inspect_release
    with pytest.raises(KnowledgeReleaseError, match="exactly the required datasets"):
        inspect_release(manifest["knowledge_release"], knowledge)


def test_active_runtime_requires_completed_audit_commit(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    log = knowledge / "promotion_events.jsonl"
    lines = log.read_text(encoding="utf-8").splitlines()
    # Simulate a crash after the pointer update but before the commit record.
    log.write_text(lines[0] + "\n", encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="no committed promotion audit event"):
        load_active_release(knowledge)


def test_promotion_audit_events_form_a_verified_chain(approved_candidate):
    from services.knowledge_release import _verified_promotion_events

    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Test release.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    events = _verified_promotion_events(knowledge / "promotion_events.jsonl")
    assert [event["event"] for event in events] == ["promote", "promote_committed"]
    assert events[1]["previous_event_sha256"] == events[0]["event_sha256"]


def test_interrupted_rollback_fails_closed_until_completion_event(approved_candidate, tmp_path, monkeypatch):
    """A crash after rollback pointer replacement must not look committed."""
    import services.knowledge_release as release_service

    candidate, curation, staging, knowledge = approved_candidate
    first = create_release([candidate["candidate_id"]], "steward", "First release.", curation, staging, knowledge)
    promote_with_task11_reviews(first, curation, staging, knowledge)

    source = tmp_path / "rollback-evidence.json"
    source.write_bytes(b'{"source":"second synthetic clinical evidence"}\n')
    evidence = ingest_json_document(source, EvidenceMetadata(
        publisher="Synthetic Publisher", source_type="other",
        document_title="Synthetic rollback release", canonical_url="https://api.fda.gov/rollback-test",
    ), staging)
    record_review_decision(evidence.record_id, "accepted_for_curation", "evidence-reviewer-2", "clinical_reviewer", "Accepted for test.", staging)
    second_candidate = create_candidate(
        "food_rule",
        {"medication": "metformin", "requirement": "with_food", "note": "Synthetic test only", "source": "Synthetic source"},
        [evidence.record_id], "second-author", "Second synthetic candidate.", staging, curation,
    )
    record_clinical_decision(second_candidate["candidate_id"], "approved", "independent-physician", "physician", "Synthetic approval.", curation, staging)
    second = create_release([second_candidate["candidate_id"]], "steward", "Second release.", curation, staging, knowledge)
    promote_with_task11_reviews(second, curation, staging, knowledge)

    append_event = release_service._append_event

    def fail_before_rollback_commit(path, event):
        if event.get("event") == "rollback_committed":
            raise OSError("simulated crash before rollback completion record")
        return append_event(path, event)

    monkeypatch.setattr(release_service, "_append_event", fail_before_rollback_commit)
    with pytest.raises(OSError, match="simulated crash"):
        rollback_release(first["knowledge_release"], "independent-rollbacker", "administrator", knowledge,
                     "Synthetic test rollback after second release.", curation, staging)

    with pytest.raises(KnowledgeReleaseError, match="no committed promotion audit event"):
        load_active_release(knowledge)



def test_promotion_requires_both_release_level_reviews(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Review-gated release.", curation, staging, knowledge)
    status = release_review_status(manifest["knowledge_release"], knowledge)
    assert status["status"] == "pending_review"
    with pytest.raises(KnowledgeReleaseError, match="requires approved clinical and governance reviews"):
        promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    record_release_review(manifest["knowledge_release"], "release-clinical-reviewer", "clinical_pharmacist",
                          "clinical_release", "approved", "Synthetic test clinical review.", knowledge)
    with pytest.raises(KnowledgeReleaseError, match="requires approved clinical and governance reviews"):
        promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    record_release_review(manifest["knowledge_release"], "release-governance-reviewer", "knowledge_steward",
                          "governance_release", "approved", "Synthetic test governance review.", knowledge)
    assert release_review_status(manifest["knowledge_release"], knowledge)["status"] == "ready_for_promotion"
    promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    assert load_active_release(knowledge)["manifest"]["knowledge_release"] == manifest["knowledge_release"]


def test_release_review_rejects_conflicted_reviewer_and_role_mismatch(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Review separation fixture.", curation, staging, knowledge)
    release_id = manifest["knowledge_release"]
    with pytest.raises(KnowledgeReleaseError, match="authors and candidate clinical approvers"):
        record_release_review(release_id, "candidate-author", "clinical_pharmacist", "clinical_release",
                              "approved", "Must be independent.", knowledge)
    with pytest.raises(KnowledgeReleaseError, match="reviewer_role"):
        record_release_review(release_id, "release-clinical-reviewer", "knowledge_steward", "clinical_release",
                              "approved", "Wrong role for review type.", knowledge)


def test_one_identity_cannot_fill_both_release_review_roles(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Distinct reviewer fixture.", curation, staging, knowledge)
    release_id = manifest["knowledge_release"]
    record_release_review(release_id, "same-human", "clinical_pharmacist", "clinical_release",
                          "approved", "Synthetic clinical review.", knowledge)
    with pytest.raises(KnowledgeReleaseError, match="cannot fill both release review roles"):
        record_release_review(release_id, "same-human", "knowledge_steward", "governance_release",
                              "approved", "Synthetic governance review.", knowledge)


def test_current_release_rejection_blocks_promotion_until_reviewer_revises(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Rejection fixture.", curation, staging, knowledge)
    release_id = manifest["knowledge_release"]
    record_release_review(release_id, "release-clinical-reviewer", "clinical_pharmacist", "clinical_release",
                          "rejected", "Synthetic reviewer rejection.", knowledge)
    record_release_review(release_id, "release-governance-reviewer", "knowledge_steward", "governance_release",
                          "approved", "Synthetic governance approval.", knowledge)
    assert release_review_status(release_id, knowledge)["status"] == "rejected"
    with pytest.raises(KnowledgeReleaseError, match="requires approved clinical and governance reviews"):
        promote_release(release_id, "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    record_release_review(release_id, "release-clinical-reviewer", "clinical_pharmacist", "clinical_release",
                          "approved", "Synthetic follow-up approval after revision.", knowledge)
    assert release_review_status(release_id, knowledge)["status"] == "ready_for_promotion"


def test_promoter_must_be_independent_from_all_authors_and_reviewers(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Promoter separation fixture.", curation, staging, knowledge)
    approve_release_for_promotion(manifest, knowledge)
    for conflicted_id in ("steward", "candidate-author", "independent-pharmacist",
                          "release-clinical-reviewer", "release-governance-reviewer"):
        with pytest.raises(KnowledgeReleaseError, match="promoter must be independent"):
            promote_release(manifest["knowledge_release"], conflicted_id, "knowledge_steward", knowledge, curation, staging)


def test_release_governance_policy_is_included_in_manifest_hashes(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Policy binding fixture.", curation, staging, knowledge)
    assert "release_governance_policy.json" in manifest["datasets"]
    release_policy = knowledge / "releases" / manifest["knowledge_release"] / "release_governance_policy.json"
    policy = json.loads(release_policy.read_text(encoding="utf-8"))
    policy["policy_id"] = "tampered-policy"
    release_policy.write_text(json.dumps(policy), encoding="utf-8")
    from services.knowledge_release import inspect_release
    with pytest.raises(KnowledgeReleaseError, match="integrity check failed: release_governance_policy.json"):
        inspect_release(manifest["knowledge_release"], knowledge)


def test_release_review_log_tampering_blocks_promotion(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Review log integrity fixture.", curation, staging, knowledge)
    approve_release_for_promotion(manifest, knowledge)
    review_log = knowledge / "release_review_events.jsonl"
    lines = review_log.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[0])
    event["reviewer_id"] = "forged-reviewer"
    lines[0] = json.dumps(event)
    review_log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="release review log integrity check failed"):
        promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)


def test_active_loader_detects_release_review_log_tampering(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Active review log fixture.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    review_log = knowledge / "release_review_events.jsonl"
    lines = review_log.read_text(encoding="utf-8").splitlines()
    event = json.loads(lines[1])
    event["rationale"] = "forged after promotion"
    lines[1] = json.dumps(event)
    review_log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(KnowledgeReleaseError, match="release review log integrity check failed"):
        load_active_release(knowledge)


def test_release_review_cannot_be_changed_after_activation(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Active immutability fixture.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    with pytest.raises(KnowledgeReleaseError, match="cannot modify release review after the release is active"):
        record_release_review(manifest["knowledge_release"], "another-reviewer", "physician", "clinical_release",
                              "approved", "Must not alter active approval state.", knowledge)


def test_rollback_requires_a_rationale(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Rollback rationale fixture.", curation, staging, knowledge)
    promote_with_task11_reviews(manifest, curation, staging, knowledge)
    with pytest.raises(KnowledgeReleaseError, match="rollback rationale is required"):
        rollback_release(manifest["knowledge_release"], "independent-rollbacker", "administrator", knowledge,
                         "", curation, staging)

def test_task06_release_without_task07_dataset_remains_inspectable_but_not_promotable(approved_candidate):
    candidate, curation, staging, knowledge = approved_candidate
    manifest = create_release([candidate["candidate_id"]], "steward", "Legacy compatibility fixture", curation, staging, knowledge)
    release_dir = knowledge / "releases" / manifest["knowledge_release"]
    legacy_manifest = json.loads((release_dir / "manifest.json").read_text(encoding="utf-8"))
    legacy_manifest.pop("task07_schema_version", None)
    legacy_manifest.pop("task08_schema_version", None)
    legacy_manifest.pop("task11_schema_version", None)
    legacy_manifest.pop("governance_context", None)
    legacy_manifest["datasets"].pop("clinical_assertions.json")
    legacy_manifest["datasets"].pop("medication_catalog.json")
    legacy_manifest["datasets"].pop("release_governance_policy.json")
    (release_dir / "clinical_assertions.json").unlink()
    (release_dir / "medication_catalog.json").unlink()
    (release_dir / "release_governance_policy.json").unlink()
    (release_dir / "manifest.json").write_text(json.dumps(legacy_manifest, indent=2), encoding="utf-8")
    from services.knowledge_release import inspect_release
    assert inspect_release(manifest["knowledge_release"], knowledge)["knowledge_release"] == manifest["knowledge_release"]
    with pytest.raises(KnowledgeReleaseError, match="predates Task 11"):
        record_release_review(manifest["knowledge_release"], "release-clinical-reviewer", "clinical_pharmacist",
                              "clinical_release", "approved", "Legacy release cannot be reviewed in place.", knowledge)
    with pytest.raises(KnowledgeReleaseError, match="predates Task 11"):
        promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward",
                        knowledge, curation, staging)
    with pytest.raises(KnowledgeReleaseError, match="no active approved"):
        load_active_release(knowledge)
