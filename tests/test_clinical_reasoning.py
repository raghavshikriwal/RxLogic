from __future__ import annotations

from models.schemas import Medication
from services.clinical_reasoning import ClinicalReasoningEngine


def _dataset(**domains):
    payload = {
        "schema_version": "1.0.0",
        "drug_food_interactions": [],
        "contraindications": [],
        "dosage_references": [],
        "administration_instructions": [],
    }
    payload.update(domains)
    return payload


def _assertion(domain, **overrides):
    base = {
        "assertion_id": "ASSERT-1",
        "medication": "warfarin",
        "review_status": "clinically_approved",
        "conflict_status": "no_known_conflict",
        "evidence_strength": "strong",
        "source_quality_tier": "high",
        "source": "Test regulator label",
        "evidence_source_ids": ["SRC-1"],
        "jurisdiction": "US",
    }
    base.update(overrides)
    return base


def test_approved_food_assertion_matches_only_explicit_food_context():
    record = _assertion("food", food_or_component="grapefruit", clinical_effect="Documented effect.", severity="moderate")
    engine = ClinicalReasoningEngine(_dataset(drug_food_interactions=[record]))
    meds = [Medication(name="warfarin")]

    missing = engine.assess(meds)
    matched = engine.assess(meds, foods=["Grapefruit"])

    assert missing["findings"] == []
    assert missing["domains"]["drug_food_interactions"]["status"] == "context_not_supplied"
    assert len(matched["findings"]) == 1
    assert matched["findings"][0]["assertion_id"] == "ASSERT-1"


def test_contraindication_requires_explicit_condition_match():
    record = _assertion("contra", condition_or_population="pregnancy", clinical_action="Requires clinician review.")
    engine = ClinicalReasoningEngine(_dataset(contraindications=[record]))
    meds = [Medication(name="warfarin")]

    assert engine.assess(meds)["findings"] == []
    result = engine.assess(meds, conditions=["pregnancy"])
    assert result["findings"][0]["domain"] == "contraindications"


def test_unreviewed_rejected_withdrawn_and_conflicted_assertions_are_never_used():
    rows = [
        _assertion("x", assertion_id="PENDING", review_status="needs_clinical_review"),
        _assertion("x", assertion_id="REJECTED", review_status="rejected"),
        _assertion("x", assertion_id="WITHDRAWN", review_status="withdrawn"),
        _assertion("x", assertion_id="CONFLICT", conflict_status="conflicting_evidence"),
        _assertion("x", assertion_id="UNASSESSED", conflict_status="not_assessed"),
    ]
    engine = ClinicalReasoningEngine(_dataset(administration_instructions=rows))
    result = engine.assess([Medication(name="warfarin")])

    assert result["findings"] == []
    assert result["excluded_assertion_counts"]["administration_instructions"] == 5
    assert [x["assertion_id"] for x in result["unresolved_conflicts"]] == ["CONFLICT"]


def test_dosage_references_are_never_emitted_as_patient_specific_dosing():
    record = _assertion(
        "dose", dose_text="Example reference dose", indication="x", population="adults",
        route="oral", frequency="daily", patient_specific=False,
    )
    engine = ClinicalReasoningEngine(_dataset(dosage_references=[record]))
    result = engine.assess([Medication(name="warfarin")])

    assert result["findings"] == []
    assert result["dosage_safety"]["matching_approved_reference_count"] == 1
    assert result["dosage_safety"]["patient_specific_dosing_generated"] is False
    assert "Example reference dose" not in str(result)


def test_empty_knowledge_does_not_claim_combination_is_safe():
    result = ClinicalReasoningEngine(_dataset()).assess(
        [Medication(name="warfarin"), Medication(name="aspirin")]
    )
    assert result["status"] == "insufficient_approved_knowledge"
    assert "not evidence" in result["interpretation"]
    assert result["clinical_use_permitted"] is False


def test_administration_instruction_only_uses_approved_conflict_assessed_record():
    record = _assertion("instruction", instruction="Use the supplied patient leaflet.")
    engine = ClinicalReasoningEngine(_dataset(administration_instructions=[record]))
    result = engine.assess([Medication(name="WARFARIN")])
    assert result["findings"][0]["message"] == "Use the supplied patient leaflet."
    assert result["findings"][0]["is_patient_specific_recommendation"] is False


def test_task09_audit_explicitly_reports_empty_knowledge_as_not_validated():
    from scripts.audit_task09 import build_report
    from pathlib import Path

    report = build_report(Path(__file__).resolve().parent.parent / "knowledge")
    assert report["clinical_validation"] is False
    assert report["clinical_use_permitted"] is False
    assert report["approved_runtime_assertions"] == 0
    assert report["empty_knowledge_probe_status"] == "insufficient_approved_knowledge"
