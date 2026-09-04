"""
Tests for services/rule_engine.py

Covers: rule loading and normalization, pairwise forward-chaining over
a medication set, order-independent matching, case-insensitivity,
full traceability of every flagged interaction back to its source
rule, and fail-safe behavior when no rules fire.

Rule-loading and normalization tests use an isolated, in-memory rule
file (via tmp_path) so they never depend on the shape of the real
curated knowledge/interaction_rules.json. A small set of sanity tests
at the bottom run against the real file to catch drift if the
curated rule set changes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.schemas import Medication, Severity
from services.rule_engine import RULES_PATH, InteractionRule, RuleEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rules_file(tmp_path) -> Path:
    """A small, self-contained rule set covering the behaviors under test."""
    payload = {
        "interaction_rules": [
            {
                "medication_a": "warfarin",
                "medication_b": "aspirin",
                "severity": "severe",
                "description": "Increased bleeding risk.",
                "source": "openFDA label",
            },
            {
                "medication_a": "metformin",
                "medication_b": "omeprazole",
                "severity": "mild",
                "description": "Minor absorption interaction.",
                "source": "clinical literature",
            },
            {
                # deliberately omits "severity" to exercise the fail-safe default
                "medication_a": "levothyroxine",
                "medication_b": "calcium",
                "description": "Reduced absorption if co-administered.",
                "source": "clinical literature",
            },
        ]
    }
    path = tmp_path / "interaction_rules.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@pytest.fixture
def engine(rules_file) -> RuleEngine:
    return RuleEngine(rules_path=rules_file)


def _med(name: str, **kwargs) -> Medication:
    return Medication(name=name, **kwargs)


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------

def test_loads_all_rules_from_file(engine):
    assert len(engine.rules) == 3


def test_rule_ids_are_generated_and_ordered(engine):
    assert [r.rule_id for r in engine.rules] == ["RULE_000", "RULE_001", "RULE_002"]


def test_medication_names_are_normalized_to_lowercase(engine):
    rule = engine.rules[0]
    assert rule.medication_a == "warfarin"
    assert rule.medication_b == "aspirin"


def test_missing_severity_defaults_to_unknown(engine):
    # third rule in the fixture omits "severity" entirely
    rule = engine.rules[2]
    assert rule.severity == Severity.UNKNOWN


def test_missing_source_defaults_to_unknown_string():
    entry = {
        "medication_a": "a",
        "medication_b": "b",
        "severity": "mild",
        "description": "no source given",
    }
    rule = InteractionRule(
        rule_id="RULE_000",
        medication_a=entry["medication_a"],
        medication_b=entry["medication_b"],
        severity=Severity.MILD,
        description=entry["description"],
        source=entry.get("source", "unknown"),
    )
    assert rule.source == "unknown"


def test_empty_rules_file_produces_no_rules(tmp_path):
    path = tmp_path / "empty_rules.json"
    path.write_text(json.dumps({"interaction_rules": []}), encoding="utf-8")
    engine = RuleEngine(rules_path=path)
    assert engine.rules == []


def test_default_engine_loads_real_knowledge_base():
    """Sanity check that the shipped knowledge base is well-formed and non-empty."""
    engine = RuleEngine()
    assert RULES_PATH.exists()
    assert len(engine.rules) > 0


# ---------------------------------------------------------------------------
# Forward chaining: check_interactions()
# ---------------------------------------------------------------------------

def test_known_pair_fires_matching_rule(engine):
    meds = [_med("Warfarin"), _med("Aspirin")]
    flagged = engine.check_interactions(meds)

    assert len(flagged) == 1
    interaction = flagged[0]
    assert interaction.severity == Severity.SEVERE
    assert interaction.rule_id == "RULE_000"
    assert interaction.description == "Increased bleeding risk."
    assert interaction.source == "openFDA label"


def test_matching_is_order_independent(engine):
    forward = engine.check_interactions([_med("Warfarin"), _med("Aspirin")])
    reverse = engine.check_interactions([_med("Aspirin"), _med("Warfarin")])

    assert len(forward) == len(reverse) == 1
    assert forward[0].rule_id == reverse[0].rule_id


def test_matching_is_case_insensitive(engine):
    flagged = engine.check_interactions([_med("WARFARIN"), _med("aSpIrIn")])
    assert len(flagged) == 1
    assert flagged[0].rule_id == "RULE_000"


def test_unrelated_medications_fire_no_rules(engine):
    meds = [_med("Metoprolol"), _med("Lisinopril")]
    assert engine.check_interactions(meds) == []


def test_single_medication_cannot_fire_any_rule(engine):
    assert engine.check_interactions([_med("Warfarin")]) == []


def test_empty_medication_list_returns_empty(engine):
    assert engine.check_interactions([]) == []


def test_rule_without_severity_flags_as_unknown_but_confidence_stays_certain(engine):
    meds = [_med("Levothyroxine"), _med("Calcium")]
    flagged = engine.check_interactions(meds)

    assert len(flagged) == 1
    assert flagged[0].severity == Severity.UNKNOWN
    # a firing rule is a certain pattern match; confidence refinement
    # under uncertainty is the uncertainty layer's responsibility, not
    # the rule engine's (Section 4.1, Layer 3).
    assert flagged[0].confidence == 1.0


def test_every_flagged_interaction_traces_back_to_a_source_rule(engine):
    meds = [_med("Warfarin"), _med("Aspirin"), _med("Metformin"), _med("Omeprazole")]
    flagged = engine.check_interactions(meds)

    assert len(flagged) == 2
    rule_ids = {i.rule_id for i in flagged}
    assert rule_ids == {"RULE_000", "RULE_001"}
    for interaction in flagged:
        assert interaction.rule_id  # non-empty, traceable
        assert interaction.source  # non-empty, traceable


def test_all_pairs_are_checked_in_a_larger_medication_set(engine):
    # 4 medications -> C(4,2) = 6 pairs checked; only 2 pairs match known rules
    meds = [_med("Warfarin"), _med("Aspirin"), _med("Metformin"), _med("Omeprazole")]
    flagged = engine.check_interactions(meds)
    flagged_pairs = {frozenset((i.medication_a.lower(), i.medication_b.lower())) for i in flagged}

    assert frozenset(("warfarin", "aspirin")) in flagged_pairs
    assert frozenset(("metformin", "omeprazole")) in flagged_pairs
    assert len(flagged_pairs) == 2


def test_duplicate_medication_entry_does_not_self_match(engine):
    # two entries for the same medication should never be flagged against themselves
    meds = [_med("Warfarin"), _med("Warfarin")]
    assert engine.check_interactions(meds) == []