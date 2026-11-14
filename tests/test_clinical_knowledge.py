from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.clinical_knowledge import validate_clinical_assertions
from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
from services.evidence_review import record_review_decision
from services.knowledge_curation import CurationError, create_candidate, record_clinical_decision
from services.knowledge_release import (
    create_release, load_active_release, promote_release, record_release_review,
)


def _approve_release(release_id: str, knowledge: Path):
    record_release_review(release_id, "release-clinical-reviewer", "clinical_pharmacist",
                          "clinical_release", "approved", "Synthetic test-only review", knowledge)
    record_release_review(release_id, "release-governance-reviewer", "knowledge_steward",
                          "governance_release", "approved", "Synthetic test-only governance approval", knowledge)


def _accepted_evidence(tmp_path: Path):
    source = tmp_path / "label.json"
    source.write_text('{"label":"synthetic fixture only"}', encoding="utf-8")
    staging = tmp_path / "staging"
    result = ingest_json_document(source, EvidenceMetadata(
        publisher="Synthetic regulator fixture", source_type="fda_label",
        document_title="Synthetic label fixture", canonical_url="https://api.fda.gov/test/task07-label",
        jurisdiction="US",
    ), staging)
    record_review_decision(result.record_id, "accepted_for_curation", "evidence-reviewer", "clinical_reviewer", "Synthetic fixture accepted.", staging)
    return staging, result


@pytest.mark.parametrize("kind,rule", [
    ("drug_food_interaction", {"medication":"metformin","food_or_component":"test food","clinical_effect":"Synthetic effect only","severity":"moderate","evidence_strength":"moderate","source":"Synthetic","jurisdiction":"US","conflict_status":"no_known_conflict"}),
    ("contraindication", {"medication":"metformin","condition_or_population":"synthetic population","clinical_action":"Synthetic action only","evidence_strength":"moderate","source":"Synthetic","jurisdiction":"US","conflict_status":"no_known_conflict"}),
    ("dosage_reference", {"medication":"metformin","indication":"synthetic indication","population":"synthetic adult population","dose_text":"See source label; synthetic fixture only","route":"oral","frequency":"per source label","evidence_strength":"moderate","source":"Synthetic","jurisdiction":"US","conflict_status":"no_known_conflict"}),
    ("administration_instruction", {"medication":"metformin","instruction":"Synthetic instruction only","evidence_strength":"moderate","source":"Synthetic","jurisdiction":"US","conflict_status":"no_known_conflict"}),
])
def test_task07_candidate_types_require_accepted_evidence_and_preserve_non_patient_specificity(tmp_path, kind, rule):
    staging, evidence = _accepted_evidence(tmp_path)
    candidate = create_candidate(kind, rule, [evidence.record_id], "author", "Synthetic test only", staging, tmp_path / "curation")
    assert candidate["candidate_type"] == kind
    assert candidate["promotion_status"] == "not_promoted"
    if kind == "dosage_reference":
        assert candidate["rule"]["patient_specific"] is False


def test_task07_candidate_cannot_be_approved_without_explicit_conflict_assessment(tmp_path):
    staging, evidence = _accepted_evidence(tmp_path)
    candidate = create_candidate("contraindication", {
        "medication":"metformin", "condition_or_population":"synthetic condition",
        "clinical_action":"synthetic only", "evidence_strength":"unknown", "source":"Synthetic",
    }, [evidence.record_id], "author", "Synthetic test", staging, tmp_path / "curation")
    with pytest.raises(CurationError, match="conflict assessment"):
        record_clinical_decision(candidate["candidate_id"], "approved", "doctor", "physician", "Review", tmp_path / "curation", staging)


def test_resolved_conflict_requires_rationale(tmp_path):
    staging, evidence = _accepted_evidence(tmp_path)
    rule = {"medication":"metformin", "condition_or_population":"synthetic condition", "clinical_action":"synthetic only", "evidence_strength":"unknown", "source":"Synthetic", "conflict_status":"resolved"}
    with pytest.raises(CurationError, match="conflict_resolution"):
        create_candidate("contraindication", rule, [evidence.record_id], "author", "Synthetic test", staging, tmp_path / "curation")


def test_clinical_assertion_validator_rejects_patient_specific_dose_and_missing_provenance():
    payload = {"schema_version":"1.0.0", "drug_food_interactions":[], "contraindications":[],
               "dosage_references":[{"assertion_id":"D1","medication":"metformin","indication":"x","population":"x","dose_text":"x","route":"oral","frequency":"daily","patient_specific":True,"review_status":"clinically_approved","evidence_strength":"strong","source_quality_tier":"high","evidence_source_ids":["SRC"]}],
               "administration_instructions":[]}
    errors = validate_clinical_assertions(payload, {"metformin"}, {"SRC"})
    assert any("patient_specific must be false" in error for error in errors)


def test_approved_task07_assertion_is_in_release_but_does_not_claim_clinical_use(tmp_path):
    staging, evidence = _accepted_evidence(tmp_path)
    curation = tmp_path / "curation"
    candidate = create_candidate("contraindication", {
        "medication":"warfarin", "condition_or_population":"synthetic condition",
        "clinical_action":"synthetic test action", "evidence_strength":"moderate", "source":"Synthetic",
        "jurisdiction":"US", "conflict_status":"no_known_conflict",
    }, [evidence.record_id], "author", "Synthetic test candidate", staging, curation)
    record_clinical_decision(candidate["candidate_id"], "approved", "independent-pharmacist", "clinical_pharmacist", "Synthetic test approval", curation, staging)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    policy = Path(__file__).resolve().parent.parent / "knowledge" / "release_governance_policy.json"
    (knowledge / "release_governance_policy.json").write_bytes(policy.read_bytes())
    (knowledge / "interaction_rules.json").write_text(json.dumps({"medications":{"warfarin":"11289"},"interaction_rules":[]}), encoding="utf-8")
    manifest = create_release([candidate["candidate_id"]], "steward", "Synthetic release", curation, staging, knowledge)
    release_file = knowledge / "releases" / manifest["knowledge_release"] / "clinical_assertions.json"
    assertions = json.loads(release_file.read_text(encoding="utf-8"))
    assert len(assertions["contraindications"]) == 1
    assert assertions["contraindications"][0]["review_status"] == "clinically_approved"
    assert manifest["publication_policy"]["clinical_use_permitted"] is False
    _approve_release(manifest["knowledge_release"], knowledge)
    promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    runtime = load_active_release(knowledge)
    assert len(runtime["clinical_assertions"]["contraindications"]) == 1
    assert runtime["manifest"]["publication_policy"]["clinical_use_permitted"] is False


def test_single_release_can_contain_all_task07_assertion_families(tmp_path):
    staging, evidence = _accepted_evidence(tmp_path)
    curation = tmp_path / "curation"
    candidates = []
    assertions = [
        ("drug_food_interaction", {"medication":"warfarin", "food_or_component":"synthetic ingredient", "clinical_effect":"synthetic effect", "severity":"moderate", "evidence_strength":"moderate", "source":"Synthetic", "jurisdiction":"US", "conflict_status":"no_known_conflict", "source_quality_tier":"high", "source_quality_rationale":"Synthetic test rationale"}),
        ("contraindication", {"medication":"warfarin", "condition_or_population":"synthetic condition", "clinical_action":"synthetic action", "evidence_strength":"moderate", "source":"Synthetic", "jurisdiction":"US", "conflict_status":"no_known_conflict"}),
        ("dosage_reference", {"medication":"warfarin", "indication":"synthetic indication", "population":"synthetic population", "dose_text":"source-specific text only", "route":"oral", "frequency":"as specified in source", "evidence_strength":"unknown", "source":"Synthetic", "jurisdiction":"US", "conflict_status":"no_known_conflict"}),
        ("administration_instruction", {"medication":"warfarin", "instruction":"synthetic instruction", "evidence_strength":"moderate", "source":"Synthetic", "jurisdiction":"US", "conflict_status":"no_known_conflict"}),
    ]
    for kind, rule in assertions:
        candidate = create_candidate(kind, rule, [evidence.record_id], f"author-{kind}", "Synthetic test assertion", staging, curation)
        record_clinical_decision(candidate["candidate_id"], "approved", "independent-pharmacist", "clinical_pharmacist", "Synthetic test review", curation, staging)
        candidates.append(candidate)
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    policy = Path(__file__).resolve().parent.parent / "knowledge" / "release_governance_policy.json"
    (knowledge / "release_governance_policy.json").write_bytes(policy.read_bytes())
    (knowledge / "interaction_rules.json").write_text(json.dumps({"medications":{"warfarin":"11289"},"interaction_rules":[]}), encoding="utf-8")
    manifest = create_release([item["candidate_id"] for item in candidates], "steward", "Synthetic full-domain release", curation, staging, knowledge)
    bundle_path = knowledge / "releases" / manifest["knowledge_release"]
    dataset = json.loads((bundle_path / "clinical_assertions.json").read_text(encoding="utf-8"))
    assert all(len(dataset[key]) == 1 for key in ("drug_food_interactions", "contraindications", "dosage_references", "administration_instructions"))
    source_data = json.loads((bundle_path / "evidence_sources.json").read_text(encoding="utf-8"))
    appraisals = source_data["sources"][0]["source_quality_assessments"]
    assert any(item["quality"] == "high" and item["rationale"] for item in appraisals)
    assert all(item["clinical_reviewer_role"] == "clinical_pharmacist" for item in appraisals)
    assert all(item["clinical_decision_id"] for item in appraisals)
    _approve_release(manifest["knowledge_release"], knowledge)
    promote_release(manifest["knowledge_release"], "independent-promoter", "knowledge_steward", knowledge, curation, staging)
    active = load_active_release(knowledge)
    assert all(len(active["clinical_assertions"][key]) == 1 for key in ("drug_food_interactions", "contraindications", "dosage_references", "administration_instructions"))


def test_task07_audit_reports_structural_governance_without_claiming_clinical_validation():
    from services.task07_audit import build_task07_audit
    root = Path(__file__).resolve().parent.parent / "knowledge"
    report = build_task07_audit(root)
    assert report["passed"] is True
    assert report["checks"]["clinical_use_prohibited"] is True
    assert report["checks"]["no_unapproved_clinical_assertions"] is True
    assert report["clinical_assertion_records_present"] is False
    assert report["clinical_assertions_are_empty_pending_review"] is True
    assert "not_clinical_validation" in report["audit_type"]
    assert report["clinical_assertion_counts"]["dosage_references"] == 0
