"""
Tests for services/csp_scheduler.py

Covers: single/multiple dose spacing, timing-preference windows,
with_food constraints, interaction-driven separation, and the
fail-safe ConstraintUnsatisfiableError path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.exceptions import ConstraintUnsatisfiableError
from models.schemas import Interaction, Medication, Severity, TimingPreference
from services.csp_scheduler import (
    DAY_END_MINUTES,
    DAY_START_MINUTES,
    MIN_INTERACTION_SEPARATION_MINUTES,
    CSPScheduler,
)


def _minutes(entry) -> int:
    return entry.scheduled_time.hour * 60 + entry.scheduled_time.minute


def test_single_medication_single_dose_within_window():
    meds = [Medication(name="Metformin", frequency_per_day=1)]
    result = CSPScheduler(meds).solve()

    assert len(result.entries) == 1
    entry = result.entries[0]
    assert entry.medication == "metformin"
    assert DAY_START_MINUTES <= _minutes(entry) <= DAY_END_MINUTES


def test_twice_daily_doses_are_spaced_apart():
    meds = [Medication(name="Metformin", frequency_per_day=2)]
    result = CSPScheduler(meds).solve()

    assert len(result.entries) == 2
    gap = abs(_minutes(result.entries[0]) - _minutes(result.entries[1]))
    # window is 16h (06:00-22:00); with slack, 2 doses should be spread by several hours
    assert gap >= 4 * 60


def test_three_times_daily_all_scheduled_and_spaced():
    meds = [Medication(name="Amoxicillin", frequency_per_day=3)]
    result = CSPScheduler(meds).solve()

    assert len(result.entries) == 3
    times = sorted(_minutes(e) for e in result.entries)
    gaps = [times[1] - times[0], times[2] - times[1]]
    assert all(gap > 0 for gap in gaps)


def test_timing_preference_is_respected():
    meds = [Medication(name="Atorvastatin", frequency_per_day=1, timing_preference=TimingPreference.NIGHT)]
    result = CSPScheduler(meds).solve()

    entry = result.entries[0]
    assert 20 * 60 <= _minutes(entry) <= DAY_END_MINUTES


def test_with_food_true_lands_near_a_meal():
    meds = [Medication(name="Ibuprofen", frequency_per_day=1, with_food=True)]
    result = CSPScheduler(meds).solve()

    entry = result.entries[0]
    meal_times = [8 * 60, 13 * 60, 20 * 60]
    assert any(abs(_minutes(entry) - meal) <= 45 for meal in meal_times)


def test_with_food_false_avoids_meal_times():
    meds = [Medication(name="Levothyroxine", frequency_per_day=1, with_food=False)]
    result = CSPScheduler(meds).solve()

    entry = result.entries[0]
    meal_times = [8 * 60, 13 * 60, 20 * 60]
    assert all(abs(_minutes(entry) - meal) >= 60 for meal in meal_times)


def test_interacting_medications_are_separated():
    meds = [
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Aspirin", frequency_per_day=1),
    ]
    interactions = [
        Interaction(
            medication_a="warfarin",
            medication_b="aspirin",
            severity=Severity.SEVERE,
            confidence=0.9,
            rule_id="R001",
            description="Increased bleeding risk",
        )
    ]
    result = CSPScheduler(meds, interactions).solve()

    by_med = {e.medication: e for e in result.entries}
    gap = abs(_minutes(by_med["warfarin"]) - _minutes(by_med["aspirin"]))
    assert gap >= MIN_INTERACTION_SEPARATION_MINUTES

    interacting_entry = by_med["warfarin"]
    assert "interaction_separation" in interacting_entry.constraint_ids


def test_non_interacting_medications_are_not_forced_apart():
    meds = [
        Medication(name="Metformin", frequency_per_day=1),
        Medication(name="Lisinopril", frequency_per_day=1),
    ]
    result = CSPScheduler(meds).solve()

    for entry in result.entries:
        assert "interaction_separation" not in entry.constraint_ids


def test_unsatisfiable_schedule_raises_constraint_error():
    # with_food=True forces the dose near a meal; NIGHT window (20:00-22:00)
    # only overlaps the dinner meal window narrowly -- pushing frequency high
    # enough exhausts that intersection and should raise, never silently guess.
    meds = [
        Medication(
            name="ImpossibleMed",
            frequency_per_day=6,
            timing_preference=TimingPreference.NIGHT,
            with_food=True,
        )
    ]
    with pytest.raises(ConstraintUnsatisfiableError):
        CSPScheduler(meds).solve()


def test_reasoning_and_constraint_ids_are_populated():
    meds = [Medication(name="Omeprazole", frequency_per_day=1, timing_preference=TimingPreference.MORNING, with_food=False)]
    result = CSPScheduler(meds).solve()

    entry = result.entries[0]
    assert entry.reasoning  # non-empty human-readable explanation
    assert any(c.startswith("timing_preference:") for c in entry.constraint_ids)
    assert any(c.startswith("with_food:") for c in entry.constraint_ids)