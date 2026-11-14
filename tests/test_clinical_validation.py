import pytest
from services.clinical_validation import (
    ClinicalValidationError, evaluate_predictions, reviewer_agreement,
    validate_validation_dataset,
)


def test_empty_validation_dataset_is_valid_but_not_evidence():
    payload = {"schema_version": "1.0.0", "cases": []}
    assert validate_validation_dataset(payload) == []
    assert evaluate_predictions([])["status"] == "not_evaluable"


def test_adjudicated_case_requires_two_independent_reviewers_and_adjudicator():
    payload = {"schema_version": "1.0.0", "cases": [{
        "case_id": "CASE-1", "case_type": "clinical_reference",
        "domain": "drug_food_interactions", "scenario": "Synthetic test scenario",
        "input_context": {"medications": ["example-drug"], "foods": ["example-food"], "conditions": []},
        "adjudication_state": "adjudicated", "reference_outcome": "finding_present",
        "reviewer_decisions": [
            {"reviewer_id": "r1", "reviewer_role": "clinical_pharmacist", "outcome": "finding_present", "rationale": "Reviewed source evidence", "evidence_source_ids": ["SRC-1"]},
            {"reviewer_id": "r2", "reviewer_role": "physician", "outcome": "finding_present", "rationale": "Reviewed source evidence", "evidence_source_ids": ["SRC-1"]},
        ],
        "reference_evidence_source_ids": ["SRC-1"],
        "adjudication": {"adjudicator_id": "r3", "adjudicator_role": "physician", "outcome": "finding_present", "rationale": "Independent adjudication"},
    }]}
    assert validate_validation_dataset(payload, source_ids={"SRC-1"}) == []
    payload["cases"][0]["adjudication"]["adjudicator_id"] = "r1"
    assert any("must be independent" in e for e in validate_validation_dataset(payload, source_ids={"SRC-1"}))


def test_unadjudicated_case_cannot_smuggle_reference_label():
    payload = {"schema_version": "1.0.0", "cases": [{
        "case_id": "CASE-1", "case_type": "clinical_reference", "domain": "contraindications",
        "scenario": "Scenario", "input_context": {"medications": ["x"], "foods": [], "conditions": ["y"]},
        "adjudication_state": "not_adjudicated", "reference_outcome": "finding_present", "reviewer_decisions": [],
    }]}
    assert any("must not have reference_outcome" in e for e in validate_validation_dataset(payload))


def test_metrics_confusion_matrix_and_zero_denominator_are_explicit():
    report = evaluate_predictions([
        {"reference_outcome": "finding_present", "predicted_outcome": "finding_present"},
        {"reference_outcome": "finding_present", "predicted_outcome": "insufficient_approved_knowledge"},
        {"reference_outcome": "insufficient_approved_knowledge", "predicted_outcome": "finding_present"},
        {"reference_outcome": "insufficient_approved_knowledge", "predicted_outcome": "insufficient_approved_knowledge"},
    ])
    assert report["confusion_matrix"] == {"true_positive": 1, "false_positive": 1, "true_negative": 1, "false_negative": 1}
    assert report["metrics"]["accuracy"] == 0.5
    assert report["metrics"]["precision"] == 0.5
    assert report["metrics"]["recall_sensitivity"] == 0.5
    with pytest.raises(ClinicalValidationError):
        evaluate_predictions([{"reference_outcome": None, "predicted_outcome": "finding_present"}])


def test_reviewer_agreement_reports_not_evaluable_when_empty():
    assert reviewer_agreement([]) == {"status": "not_evaluable", "n": 0, "raw_agreement": None, "cohens_kappa": None}


def test_reviewer_agreement_handles_perfect_agreement_with_undefined_kappa():
    report = reviewer_agreement([{"case_type": "clinical_reference", "reviewer_decisions": [
        {"outcome": "finding_present"}, {"outcome": "finding_present"}
    ]}])
    assert report["raw_agreement"] == 1.0
    assert report["cohens_kappa"] is None
