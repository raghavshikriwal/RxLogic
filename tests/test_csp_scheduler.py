"""
Tests for services/csp_scheduler.py

Covers: single/multiple dose spacing, timing-preference windows,
with_food constraints, interaction-driven separation, deterministic
backtracking retry behavior, and the fail-safe
ConstraintUnsatisfiableError path.
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
    """Return the scheduled time as minutes after midnight."""
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

    # The scheduling window is 16 hours (06:00-22:00).
    # With the configured spacing slack, two doses should be separated
    # by several hours rather than clustered together.
    assert gap >= 4 * 60


def test_three_times_daily_all_scheduled_and_spaced():
    meds = [Medication(name="Amoxicillin", frequency_per_day=3)]
    result = CSPScheduler(meds).solve()

    assert len(result.entries) == 3

    times = sorted(_minutes(entry) for entry in result.entries)
    gaps = [
        times[1] - times[0],
        times[2] - times[1],
    ]

    assert all(gap > 0 for gap in gaps)


def test_timing_preference_is_respected():
    meds = [
        Medication(
            name="Atorvastatin",
            frequency_per_day=1,
            timing_preference=TimingPreference.NIGHT,
        )
    ]

    result = CSPScheduler(meds).solve()

    entry = result.entries[0]

    assert 20 * 60 <= _minutes(entry) <= DAY_END_MINUTES


def test_with_food_true_lands_near_a_meal():
    meds = [
        Medication(
            name="Ibuprofen",
            frequency_per_day=1,
            with_food=True,
        )
    ]

    result = CSPScheduler(meds).solve()

    entry = result.entries[0]

    meal_times = [
        8 * 60,
        13 * 60,
        20 * 60,
    ]

    assert any(
        abs(_minutes(entry) - meal) <= 45
        for meal in meal_times
    )


def test_with_food_false_avoids_meal_times():
    meds = [
        Medication(
            name="Levothyroxine",
            frequency_per_day=1,
            with_food=False,
        )
    ]

    result = CSPScheduler(meds).solve()

    entry = result.entries[0]

    meal_times = [
        8 * 60,
        13 * 60,
        20 * 60,
    ]

    assert all(
        abs(_minutes(entry) - meal) >= 60
        for meal in meal_times
    )


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

    by_med = {
        entry.medication: entry
        for entry in result.entries
    }

    gap = abs(
        _minutes(by_med["warfarin"])
        - _minutes(by_med["aspirin"])
    )

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
    # with_food=True requires a dose near a meal, while NIGHT restricts
    # the domain to 20:00-22:00. A frequency of six doses exhausts the
    # feasible combination and must fail safely.
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


def test_backtracking_recovers_when_first_candidate_conflicts():
    """
    Integration-style test for the scheduler's backtracking behavior.

    Every medication interacts with every other medication, so the solver
    must find a schedule satisfying all pairwise separation constraints.
    """
    meds = [
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Aspirin", frequency_per_day=1),
        Medication(name="Ibuprofen", frequency_per_day=1),
    ]

    interactions = [
        Interaction(
            medication_a="warfarin",
            medication_b="aspirin",
            severity=Severity.SEVERE,
            confidence=0.9,
            rule_id="R001",
            description="Increased bleeding risk",
        ),
        Interaction(
            medication_a="warfarin",
            medication_b="ibuprofen",
            severity=Severity.SEVERE,
            confidence=0.9,
            rule_id="R002",
            description="Increased bleeding/GI risk",
        ),
        Interaction(
            medication_a="aspirin",
            medication_b="ibuprofen",
            severity=Severity.MODERATE,
            confidence=0.7,
            rule_id="R003",
            description="Reduced antiplatelet effect",
        ),
    ]

    result = CSPScheduler(meds, interactions).solve()

    by_med = {
        entry.medication: entry
        for entry in result.entries
    }

    assert len(by_med) == 3

    pairs = [
        ("warfarin", "aspirin"),
        ("warfarin", "ibuprofen"),
        ("aspirin", "ibuprofen"),
    ]

    for med_a, med_b in pairs:
        gap = abs(
            _minutes(by_med[med_a])
            - _minutes(by_med[med_b])
        )

        assert gap >= MIN_INTERACTION_SEPARATION_MINUTES


def test_consistent_rejects_a_value_that_violates_the_gap_constraint():
    """
    Deterministic white-box test for _consistent().

    An interacting medication pair must be separated by at least
    MIN_INTERACTION_SEPARATION_MINUTES.
    """
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

    scheduler = CSPScheduler(
        meds,
        interactions,
    )

    warfarin_var = next(
        variable
        for variable in scheduler.variables
        if variable.medication == "warfarin"
    )

    aspirin_var = next(
        variable
        for variable in scheduler.variables
        if variable.medication == "aspirin"
    )

    assignment = {
        aspirin_var.name: 8 * 60,
    }

    # 08:30 is only 30 minutes from 08:00 and therefore violates
    # the required 120-minute interaction separation.
    assert (
        scheduler._consistent(
            warfarin_var,
            8 * 60 + 30,
            assignment,
        )
        is False
    )

    # 12:00 is four hours later and therefore satisfies the constraint.
    assert (
        scheduler._consistent(
            warfarin_var,
            12 * 60,
            assignment,
        )
        is True
    )


def test_backtrack_loop_hits_inconsistent_continue_branch():
    """
    Deterministically exercises the `continue` statement in _backtrack().

    Important detail:
    _forward_check() normally removes inconsistent values before the
    recursive _backtrack() call. To test the explicit `continue` branch,
    we enter _backtrack() with the first variable already assigned.

    Search sequence:

        Warfarin = 08:00
        Aspirin  = 08:20  -> _consistent() returns False -> continue
        Aspirin  = 12:00  -> _consistent() returns True
        complete assignment

    This directly covers the branch at line 200 without mocking the
    constraint logic or changing production code.
    """
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
            description="Bleeding risk",
        )
    ]

    scheduler = CSPScheduler(
        meds,
        interactions,
    )

    warfarin_var = next(
        variable
        for variable in scheduler.variables
        if variable.medication == "warfarin"
    )

    aspirin_var = next(
        variable
        for variable in scheduler.variables
        if variable.medication == "aspirin"
    )

    warfarin_time = 8 * 60
    invalid_aspirin_time = 8 * 60 + 20
    valid_aspirin_time = 12 * 60

    # Simulate the state immediately before _backtrack() begins
    # searching for the second medication.
    assignment = {
        warfarin_var.name: warfarin_time,
    }

    # Deliberately retain both candidates. Because this assignment was
    # supplied directly, _forward_check() has not removed the invalid
    # candidate yet. This makes _consistent() responsible for rejecting it.
    domains = {
        warfarin_var.name: [warfarin_time],
        aspirin_var.name: [
            invalid_aspirin_time,
            valid_aspirin_time,
        ],
    }

    solution = scheduler._backtrack(
        assignment,
        domains,
    )

    assert solution == {
        warfarin_var.name: warfarin_time,
        aspirin_var.name: valid_aspirin_time,
    }


def test_same_medication_min_gap_is_zero_for_a_single_dose():
    """
    Defensive white-box test for the dose_count <= 1 guard.
    """
    scheduler = CSPScheduler(
        [
            Medication(
                name="Metformin",
                frequency_per_day=1,
            )
        ]
    )

    assert scheduler._same_medication_min_gap("metformin") == 0


def test_reasoning_and_constraint_ids_are_populated():
    meds = [
        Medication(
            name="Omeprazole",
            frequency_per_day=1,
            timing_preference=TimingPreference.MORNING,
            with_food=False,
        )
    ]

    result = CSPScheduler(meds).solve()

    entry = result.entries[0]

    assert entry.reasoning

    assert any(
        constraint.startswith("timing_preference:")
        for constraint in entry.constraint_ids
    )

    assert any(
        constraint.startswith("with_food:")
        for constraint in entry.constraint_ids
    )