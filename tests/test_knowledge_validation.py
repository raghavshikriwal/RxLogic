from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.knowledge_validation import ROOT, validate_knowledge


def test_shipped_knowledge_release_is_structurally_valid():
    assert validate_knowledge(ROOT) == []


def test_migrated_interaction_rules_have_stable_ids_and_review_state():
    data = json.loads((ROOT / "interaction_rules.json").read_text(encoding="utf-8"))
    rules = data["interaction_rules"]
    assert len({rule["rule_id"] for rule in rules}) == len(rules)
    assert all(rule["review_status"] == "needs_clinical_review" for rule in rules)
    assert all(rule["evidence_source_ids"] for rule in rules)


def test_legacy_source_labels_are_explicitly_unverified():
    data = json.loads((ROOT / "evidence_sources.json").read_text(encoding="utf-8"))
    legacy = [s for s in data["sources"] if s["source_id"].startswith("SRC-LEGACY-")]
    assert legacy
    assert all(source["verification_status"] == "unverified" for source in legacy)
    assert all(source["locator"] is None for source in legacy)


def test_rule_engine_uses_stable_ids_for_migrated_dataset():
    from services.rule_engine import RuleEngine
    engine = RuleEngine()
    assert all(rule.rule_id.startswith("DDI-") for rule in engine.rules)


def test_interaction_result_exposes_provenance_and_review_state():
    from models.schemas import Medication
    from services.rule_engine import RuleEngine

    engine = RuleEngine()
    result = engine.check_interactions([Medication("warfarin"), Medication("aspirin")])[0]
    assert result.rule_id == "DDI-ASPIRIN-WARFARIN"
    assert result.evidence_source_ids
    assert result.review_status == "needs_clinical_review"
    assert result.jurisdiction == "unspecified"


def test_food_rule_retains_provenance_and_review_state():
    from services.food_rules import FoodRules

    guidance = FoodRules().apply([])[1]
    assert guidance == []
    rules = FoodRules().rules
    metformin = rules["metformin"]
    assert metformin.rule_id == "FOOD-METFORMIN"
    assert metformin.evidence_source_ids
    assert metformin.review_status == "needs_clinical_review"


def test_manifest_must_declare_task07_clinical_assertions_dataset(tmp_path):
    import shutil
    for name in ("manifest.json", "interaction_rules.json", "food_rules.json", "evidence_sources.json", "clinical_assertions.json"):
        shutil.copy(ROOT / name, tmp_path / name)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["datasets"].pop("clinical_assertions")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert any("clinical_assertions dataset must declare" in error for error in validate_knowledge(tmp_path))
