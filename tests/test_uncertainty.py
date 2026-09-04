"""
Tests for services/uncertainty.py

Covers: confidence ordering by severity/reliability, that severity
itself is never mutated, the polypharmacy penalty, and the confidence
floor/ceiling bounds.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import Interaction, Severity
from services.uncertainty import UncertaintyLayer, refine_confidence


def _interaction(severity: Severity, source: str = "openFDA label / clinical literature") -> Interaction:
    return Interaction(
        medication_a="warfarin",
        medication_b="aspirin",
        severity=severity,
        confidence=1.0,  # pre-refinement placeholder, as set by rule_engine.py
        rule_id="RULE_TEST",
        description="test interaction",
        source=source,
    )


def test_severity_is_never_mutated_by_refinement():
    interaction = _interaction(Severity.SEVERE)
    refined = refine_confidence([interaction], total_medication_count=2)

    assert refined[0].severity == Severity.SEVERE
    assert refined[0].medication_a == interaction.medication_a
    assert refined[0].rule_id == interaction.rule_id


def test_severe_interaction_yields_higher_confidence_than_mild():
    severe = refine_confidence([_interaction(Severity.SEVERE)], total_medication_count=2)[0]
    mild = refine_confidence([_interaction(Severity.MILD)], total_medication_count=2)[0]

    assert severe.confidence > mild.confidence


def test_higher_reliability_source_yields_higher_confidence():
    reliable = refine_confidence(
        [_interaction(Severity.MODERATE, source="openFDA label / clinical literature")],
        total_medication_count=2,
    )[0]
    less_reliable = refine_confidence(
        [_interaction(Severity.MODERATE, source="clinical literature")],
        total_medication_count=2,
    )[0]

    assert reliable.confidence > less_reliable.confidence


def test_unknown_source_falls_back_to_default_reliability():
    # should not raise, and should fall between the known high/low sources
    result = refine_confidence(
        [_interaction(Severity.MODERATE, source="some unlisted source")],
        total_medication_count=2,
    )
    assert 0.0 <= result[0].confidence <= 1.0


def test_polypharmacy_penalty_reduces_confidence():
    low_med_count = refine_confidence([_interaction(Severity.SEVERE)], total_medication_count=2)[0]
    high_med_count = refine_confidence([_interaction(Severity.SEVERE)], total_medication_count=10)[0]

    assert high_med_count.confidence < low_med_count.confidence


def test_confidence_stays_within_bounds():
    for severity in Severity:
        result = refine_confidence([_interaction(severity)], total_medication_count=15)[0]
        assert 0.0 <= result.confidence <= 1.0


def test_refine_handles_empty_interaction_list():
    assert refine_confidence([], total_medication_count=3) == []


def test_layer_reusable_across_multiple_refine_calls():
    layer = UncertaintyLayer()
    first = layer.refine([_interaction(Severity.SEVERE)], total_medication_count=2)
    second = layer.refine([_interaction(Severity.MILD)], total_medication_count=2)

    assert first[0].severity == Severity.SEVERE
    assert second[0].severity == Severity.MILD