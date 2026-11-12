from __future__ import annotations

import json
from pathlib import Path

from services.knowledge_coverage import (
    ASSERTION_PRESENT,
    NOT_EVALUATED,
    build_coverage_report,
)


def _fixture_root(tmp_path: Path) -> Path:
    root = tmp_path / "knowledge"
    root.mkdir()
    interactions = {
        "knowledge_release": "fixture-release",
        "medications": {"alpha": "1", "beta": "2", "gamma": "3"},
        "interaction_rules": [{
            "medication_a": "alpha", "medication_b": "beta", "rule_id": "DDI-AB",
            "evidence": "strong", "review_status": "needs_clinical_review",
            "evidence_source_ids": ["SRC-1"],
        }],
    }
    foods = {"food_rules": [{
        "medication": "alpha", "rule_id": "FOOD-A", "review_status": "needs_clinical_review",
        "evidence_source_ids": ["SRC-1"],
    }]}
    sources = {"sources": [{"source_id": "SRC-1", "verification_status": "unverified"}]}
    for name, payload in (("interaction_rules.json", interactions), ("food_rules.json", foods), ("evidence_sources.json", sources)):
        (root / name).write_text(json.dumps(payload), encoding="utf-8")
    return root


def test_all_unordered_pairs_are_accounted_for_and_missing_is_not_evaluated(tmp_path):
    report = build_coverage_report(_fixture_root(tmp_path))
    ddi = report["drug_drug_interactions"]
    assert ddi["counts"]["total"] == 3
    assert ddi["counts"]["assertion_present_unreviewed"] == 1
    assert ddi["counts"]["not_evaluated"] == 2
    statuses = {(p["medication_a"], p["medication_b"]): p["status"] for p in ddi["pairs"]}
    assert statuses[("alpha", "beta")] == ASSERTION_PRESENT
    assert statuses[("alpha", "gamma")] == NOT_EVALUATED
    assert statuses[("beta", "gamma")] == NOT_EVALUATED


def test_legacy_source_verification_is_not_misrepresented_as_quality(tmp_path):
    report = build_coverage_report(_fixture_root(tmp_path))
    evidence = report["drug_drug_interactions"]["pairs"][0]["evidence"][0]
    assert evidence["source_verification_state"] == "unverified"
    assert evidence["source_quality_assessment"] == "not_assessed"


def test_unassessed_domains_are_explicit_and_do_not_claim_safety(tmp_path):
    report = build_coverage_report(_fixture_root(tmp_path))
    for domain in ("contraindications", "dosage_references", "administration_instructions"):
        assert report[domain]["counts"]["not_evaluated"] == 3
        assert all(row["status"] == NOT_EVALUATED for row in report[domain]["medications"])
    assert report["drug_food_interactions"]["counts"]["not_evaluated"] == 3
    assert report["drug_food_interactions"]["enumeration_status"] == "medication_level_only"
    assert report["drug_food_interactions"]["component_denominator"] is None
    assert any("does not mean" in line for line in report["interpretation"])


def test_reviewed_and_conflicting_assertion_states_are_preserved(tmp_path):
    root = _fixture_root(tmp_path)
    path = root / "interaction_rules.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["interaction_rules"][0]["review_status"] = "clinically_approved"
    payload["interaction_rules"][0]["conflicting_evidence"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = build_coverage_report(root)
    assert report["drug_drug_interactions"]["counts"]["conflicting_evidence"] == 1
    assert report["drug_drug_interactions"]["counts"]["assertion_present_reviewed"] == 0


def test_current_dataset_inventory_counts_expected_pairs():
    root = Path(__file__).resolve().parent.parent / "knowledge"
    report = build_coverage_report(root)
    assert report["medication_count"] == 10
    assert report["drug_drug_interactions"]["counts"]["total"] == 45
    assert report["drug_drug_interactions"]["counts"]["assertion_present_unreviewed"] == 12
    assert report["drug_drug_interactions"]["counts"]["not_evaluated"] == 33
    assert report["drug_food_guidance"]["counts"]["assertion_present_unreviewed"] == 4
    assert report["drug_food_guidance"]["counts"]["not_evaluated"] == 6
