"""
Tests for services/food_rules.py

Covers: rule loading and validation, filling an open `with_food` from a
drug's rule, precedence of the user's own choice (kept and flagged on
conflict), pass-through of drugs without a rule, and a drift check on the
real curated knowledge/food_rules.json.

Behavioral tests use an isolated rule file (via tmp_path) so they never
depend on the contents of the real file.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.schemas import FoodRequirement, FoodStatus, Medication
from services.food_rules import FOOD_RULES_PATH, FoodRules
from services.rule_engine import RuleEngine


def _write_rules(tmp_path: Path, rules: list[dict]) -> Path:
    path = tmp_path / "food_rules.json"
    path.write_text(json.dumps({"food_rules": rules}), encoding="utf-8")
    return path


@pytest.fixture
def food_rules(tmp_path) -> FoodRules:
    return FoodRules(
        _write_rules(
            tmp_path,
            [
                {"medication": "Metformin", "requirement": "with_food", "note": "With meals.", "source": "label"},
                {"medication": "levothyroxine", "requirement": "empty_stomach"},
                {"medication": "warfarin", "requirement": "no_restriction", "note": "Keep vitamin K steady."},
            ],
        )
    )


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def test_rule_names_are_normalized_to_lowercase(food_rules):
    assert set(food_rules.rules) == {"metformin", "levothyroxine", "warfarin"}


def test_note_and_source_are_optional(food_rules):
    rule = food_rules.rules["levothyroxine"]

    assert rule.note == ""
    assert rule.source == ""


def test_invalid_requirement_is_rejected(tmp_path):
    path = _write_rules(tmp_path, [{"medication": "a", "requirement": "sometimes"}])

    with pytest.raises(ValueError):
        FoodRules(path)


def test_duplicate_rule_for_one_drug_is_rejected(tmp_path):
    path = _write_rules(
        tmp_path,
        [
            {"medication": "a", "requirement": "with_food"},
            {"medication": "A", "requirement": "empty_stomach"},
        ],
    )

    with pytest.raises(ValueError, match="duplicate"):
        FoodRules(path)


# ---------------------------------------------------------------------------
# Applying rules
# ---------------------------------------------------------------------------

def test_open_with_food_is_filled_from_a_with_food_rule(food_rules):
    meds, guidance = food_rules.apply([Medication(name="Metformin")])

    assert meds[0].with_food is True
    assert guidance[0].status == FoodStatus.APPLIED


def test_open_with_food_is_filled_from_an_empty_stomach_rule(food_rules):
    meds, guidance = food_rules.apply([Medication(name="Levothyroxine")])

    assert meds[0].with_food is False
    assert guidance[0].requirement == FoodRequirement.EMPTY_STOMACH


def test_user_choice_matching_the_rule_is_reported_as_a_match(food_rules):
    meds, guidance = food_rules.apply([Medication(name="metformin", with_food=True)])

    assert meds[0].with_food is True
    assert guidance[0].status == FoodStatus.MATCHES_INPUT


def test_conflicting_user_choice_is_kept_and_flagged(food_rules):
    meds, guidance = food_rules.apply([Medication(name="levothyroxine", with_food=True)])

    assert meds[0].with_food is True  # never overridden
    assert guidance[0].status == FoodStatus.CONFLICTS_WITH_INPUT


def test_no_restriction_rule_leaves_with_food_alone_and_is_informational(food_rules):
    meds, guidance = food_rules.apply([Medication(name="warfarin")])

    assert meds[0].with_food is None
    assert guidance[0].status == FoodStatus.INFORMATIONAL
    assert guidance[0].note == "Keep vitamin K steady."


def test_drug_without_a_rule_passes_through_with_no_guidance(food_rules):
    original = Medication(name="Aspirin")

    meds, guidance = food_rules.apply([original])

    assert meds == [original]
    assert guidance == []


def test_guidance_follows_input_order_and_names_are_lowercase(food_rules):
    _, guidance = food_rules.apply(
        [Medication(name="Warfarin"), Medication(name="Aspirin"), Medication(name="METFORMIN")]
    )

    assert [g.medication for g in guidance] == ["warfarin", "metformin"]


def test_other_medication_fields_are_preserved(food_rules):
    original = Medication(name="Metformin", dosage_mg=500, frequency_per_day=2)

    meds, _ = food_rules.apply([original])

    assert meds[0].dosage_mg == 500
    assert meds[0].frequency_per_day == 2


# ---------------------------------------------------------------------------
# Real knowledge base
# ---------------------------------------------------------------------------

def test_every_real_food_rule_names_a_drug_the_knowledge_base_covers():
    # a rule for a drug the engine rejects as unknown could never fire
    known = RuleEngine().known_medications

    assert set(FoodRules(FOOD_RULES_PATH).rules) <= known


def test_real_rules_encode_the_expected_meal_guidance():
    rules = FoodRules(FOOD_RULES_PATH).rules

    assert rules["metformin"].requirement == FoodRequirement.WITH_FOOD
    assert rules["levothyroxine"].requirement == FoodRequirement.EMPTY_STOMACH
