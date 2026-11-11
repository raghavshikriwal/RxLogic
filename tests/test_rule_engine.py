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

from models.schemas import DoseOrdering, EvidenceStrength, Medication, Severity
from services.rule_engine import RULES_PATH, InteractionRule, RuleEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rules_file(tmp_path) -> Path:
    """A small, self-contained rule set covering the behaviors under test."""
    payload = {
        "medications": {
            "warfarin": "11289",
            "Aspirin": "1191",  # mixed case on purpose: lookups must be case-insensitive
            "metformin": "6809",
            "omeprazole": "7646",
        },
        "interaction_rules": [
            {
                "medication_a": "warfarin",
                "medication_b": "aspirin",
                "severity": "severe",
                "evidence": "strong",
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


def test_evidence_is_loaded_from_the_rule(engine):
    assert engine.rules[0].evidence == EvidenceStrength.STRONG


def test_missing_evidence_defaults_to_unknown(engine):
    # the second fixture rule omits "evidence" entirely
    assert engine.rules[1].evidence == EvidenceStrength.UNKNOWN


def test_invalid_evidence_value_is_rejected(tmp_path):
    path = tmp_path / "bad_rules.json"
    path.write_text(
        json.dumps({
            "interaction_rules": [{
                "medication_a": "a",
                "medication_b": "b",
                "evidence": "certain",
                "description": "bad evidence label",
            }]
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        RuleEngine(rules_path=path)


def test_flagged_interaction_carries_rule_evidence_and_severity_independently(engine):
    flagged = engine.check_interactions([_med("Warfarin"), _med("Aspirin")])

    assert flagged[0].severity == Severity.SEVERE
    assert flagged[0].evidence == EvidenceStrength.STRONG


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


def test_real_knowledge_base_has_no_duplicate_pairs():
    """Structural integrity: no medication pair should be covered by more than
    one rule, regardless of the order the pair is written in the source file.
    Catches accidental double-entry when the curated set is expanded."""
    engine = RuleEngine()
    seen_pairs = set()
    for rule in engine.rules:
        pair = frozenset((rule.medication_a, rule.medication_b))
        assert pair not in seen_pairs, f"duplicate interaction pair: {pair}"
        seen_pairs.add(pair)


@pytest.mark.parametrize(
    "medication_a, medication_b",
    [
        ("warfarin", "amoxicillin"),
        ("warfarin", "omeprazole"),
        ("warfarin", "levothyroxine"),
        ("warfarin", "atorvastatin"),
        ("aspirin", "ibuprofen"),
        ("lisinopril", "ibuprofen"),
        ("metoprolol", "ibuprofen"),
        ("omeprazole", "levothyroxine"),
        ("lisinopril", "metformin"),
        ("lisinopril", "metoprolol"),
    ],
)
def test_real_knowledge_base_covers_expanded_curated_pairs(medication_a, medication_b):
    """Drift detection for the expanded rule set (Section: knowledge base
    coverage). Each pair below was curated to extend coverage beyond the
    original 8 rules using only medications already in the seed roster, so
    every one of them must fire against the shipped knowledge base."""
    engine = RuleEngine()
    flagged = engine.check_interactions([_med(medication_a), _med(medication_b)])

    assert len(flagged) == 1, f"expected exactly one rule to fire for {medication_a} + {medication_b}"
    assert flagged[0].severity != Severity.UNKNOWN


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


def test_every_real_rule_declares_evidence():
    # a rule shipped without an evidence rating would silently get the
    # lowest confidence, so the curated file must never omit it
    engine = RuleEngine(rules_path=RULES_PATH)

    assert all(rule.evidence != EvidenceStrength.UNKNOWN for rule in engine.rules)


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


# ---------------------------------------------------------------------------
# Knowledge-base coverage (fail-safe: unknown != interaction-free)
# ---------------------------------------------------------------------------

def test_known_medications_are_loaded_lowercased(engine):
    assert engine.known_medications == frozenset({"warfarin", "aspirin", "metformin", "omeprazole"})


def test_known_medications_is_empty_when_file_has_no_medications_map(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"interaction_rules": []}), encoding="utf-8")

    assert RuleEngine(rules_path=path).known_medications == frozenset()


def test_find_unknown_medications_returns_empty_when_all_are_covered(engine):
    assert engine.find_unknown_medications([_med("Warfarin"), _med("ASPIRIN")]) == []


def test_find_unknown_medications_flags_uncovered_drug(engine):
    assert engine.find_unknown_medications([_med("Warfarin"), _med("Zolpidem")]) == ["Zolpidem"]


def test_find_unknown_medications_preserves_input_order_and_original_spelling(engine):
    meds = [_med("Zolpidem"), _med("Warfarin"), _med("Xanax")]
    assert engine.find_unknown_medications(meds) == ["Zolpidem", "Xanax"]


def test_find_unknown_medications_deduplicates_case_insensitively(engine):
    meds = [_med("Zolpidem"), _med("zolpidem"), _med("ZOLPIDEM")]
    assert engine.find_unknown_medications(meds) == ["Zolpidem"]


def test_unpadded_names_only_are_recognized_so_matching_and_coverage_agree(engine):
    # " warfarin" would never match a rule in _matches, so it must not
    # count as covered either -- otherwise it would pass as "no interactions".
    assert engine.find_unknown_medications([_med(" warfarin")]) == [" warfarin"]


def test_real_knowledge_base_every_rule_drug_is_a_known_medication():
    engine = RuleEngine(rules_path=RULES_PATH)
    rule_drugs = {name for rule in engine.rules for name in (rule.medication_a, rule.medication_b)}

    assert rule_drugs <= engine.known_medications


# ---------------------------------------------------------------------------
# Coverage assessment
# ---------------------------------------------------------------------------

def test_assess_coverage_is_complete_when_every_drug_is_known(engine):
    coverage = engine.assess_coverage([_med("Warfarin"), _med("ASPIRIN")])

    assert coverage.total == 2
    assert coverage.is_complete
    assert coverage.unchecked == ()


def test_assess_coverage_lists_unknown_drugs_as_unchecked(engine):
    coverage = engine.assess_coverage([_med("Warfarin"), _med("Zolpidem"), _med("Xanax")])

    assert coverage.total == 3
    assert coverage.checked == 1
    assert coverage.unchecked == ("Zolpidem", "Xanax")


def test_assess_coverage_counts_distinct_drugs_case_insensitively(engine):
    coverage = engine.assess_coverage([_med("Warfarin"), _med("warfarin"), _med("Aspirin")])

    assert coverage.total == 2
    assert coverage.is_complete


def test_assess_coverage_of_empty_list_is_zero_of_zero(engine):
    coverage = engine.assess_coverage([])

    assert coverage.total == 0
    assert coverage.is_complete


# ---------------------------------------------------------------------------
# Per-pair separation times
# ---------------------------------------------------------------------------

def _engine_with_rule(tmp_path, **fields) -> RuleEngine:
    """Builds an engine around one a+b rule carrying the given extra fields."""
    rule = {"medication_a": "a", "medication_b": "b", "description": "test rule", **fields}
    path = tmp_path / "separation_rules.json"
    path.write_text(json.dumps({"interaction_rules": [rule]}), encoding="utf-8")
    return RuleEngine(rules_path=path)


def test_separation_is_loaded_from_the_rule(tmp_path):
    engine = _engine_with_rule(tmp_path, separation_minutes=480)

    assert engine.rules[0].separation_minutes == 480


def test_missing_separation_defaults_to_none(engine):
    assert all(rule.separation_minutes is None for rule in engine.rules)


@pytest.mark.parametrize("bad_value", [0, -30, 1.5, "120", True])
def test_invalid_separation_value_is_rejected(tmp_path, bad_value):
    with pytest.raises(ValueError, match="separation_minutes"):
        _engine_with_rule(tmp_path, separation_minutes=bad_value)


def test_flagged_interaction_carries_the_rule_separation(tmp_path):
    engine = _engine_with_rule(tmp_path, separation_minutes=240)

    flagged = engine.check_interactions([_med("a"), _med("b")])

    assert flagged[0].separation_minutes == 240


def test_real_aspirin_ibuprofen_rule_is_order_aware():
    # Ibuprofen blocks aspirin's antiplatelet effect unless it is taken at
    # least 30 min after, or well (8 h) before, the aspirin dose.
    flagged = RuleEngine().check_interactions([_med("Aspirin"), _med("Ibuprofen")])

    assert flagged[0].ordering == DoseOrdering(anchor="aspirin", after_minutes=30, before_minutes=480)
    assert flagged[0].separation_minutes is None


# ---------------------------------------------------------------------------
# Order-aware separation
# ---------------------------------------------------------------------------

_VALID_ORDERING = {"anchor": "a", "after_minutes": 30, "before_minutes": 480}


def test_ordering_is_loaded_from_the_rule(tmp_path):
    engine = _engine_with_rule(tmp_path, ordering=_VALID_ORDERING)

    assert engine.rules[0].ordering == DoseOrdering(anchor="a", after_minutes=30, before_minutes=480)


def test_ordering_anchor_is_normalized_to_lowercase(tmp_path):
    engine = _engine_with_rule(tmp_path, ordering={**_VALID_ORDERING, "anchor": "A"})

    assert engine.rules[0].ordering.anchor == "a"


def test_missing_ordering_defaults_to_none(engine):
    assert all(rule.ordering is None for rule in engine.rules)


@pytest.mark.parametrize("anchor", ["c", ""])
def test_ordering_anchor_must_be_one_of_the_rules_drugs(tmp_path, anchor):
    with pytest.raises(ValueError, match="anchor"):
        _engine_with_rule(tmp_path, ordering={**_VALID_ORDERING, "anchor": anchor})


@pytest.mark.parametrize("key", ["after_minutes", "before_minutes"])
@pytest.mark.parametrize("bad_value", [0, -5, 1.5, "30", True, None])
def test_invalid_ordering_gap_is_rejected(tmp_path, key, bad_value):
    with pytest.raises(ValueError, match=key):
        _engine_with_rule(tmp_path, ordering={**_VALID_ORDERING, key: bad_value})


def test_ordering_and_separation_on_one_rule_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="not both"):
        _engine_with_rule(tmp_path, ordering=_VALID_ORDERING, separation_minutes=120)


def test_flagged_interaction_carries_the_rule_ordering(tmp_path):
    engine = _engine_with_rule(tmp_path, ordering=_VALID_ORDERING)

    flagged = engine.check_interactions([_med("a"), _med("b")])

    assert flagged[0].ordering == DoseOrdering(anchor="a", after_minutes=30, before_minutes=480)
