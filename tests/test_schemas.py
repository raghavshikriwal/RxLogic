"""Tests for models/schemas.py -- the Coverage and Interaction value objects."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.schemas import Coverage, DailyPlan, DoseOrdering, Interaction, Severity


def test_full_coverage_reports_every_drug_checked():
    coverage = Coverage(total=6)

    assert coverage.checked == 6
    assert coverage.is_complete
    assert coverage.summary == "6 of 6 drugs checked"


def test_partial_coverage_reports_unchecked_drugs():
    coverage = Coverage(total=3, unchecked=("Zolpidem",))

    assert coverage.checked == 2
    assert not coverage.is_complete
    assert coverage.summary == "2 of 3 drugs checked"


def test_summary_uses_singular_noun_for_a_single_drug():
    assert Coverage(total=1).summary == "1 of 1 drug checked"


@pytest.mark.parametrize("total, unchecked", [(-1, ()), (1, ("a", "b"))])
def test_invalid_coverage_is_rejected(total, unchecked):
    with pytest.raises(ValueError):
        Coverage(total=total, unchecked=unchecked)


def test_daily_plan_coverage_defaults_to_none_outside_the_pipeline():
    assert DailyPlan(entries=[]).coverage is None


def test_interaction_separation_defaults_to_none():
    interaction = Interaction(
        medication_a="a",
        medication_b="b",
        severity=Severity.MILD,
        confidence=1.0,
        rule_id="R",
        description="d",
    )

    assert interaction.separation_minutes is None


def test_interaction_ordering_defaults_to_none():
    interaction = Interaction(
        medication_a="a",
        medication_b="b",
        severity=Severity.MILD,
        confidence=1.0,
        rule_id="R",
        description="d",
    )

    assert interaction.ordering is None


# anchor dose at minute 600; the other dose is safe >= 30 min after or >= 480 min before
@pytest.mark.parametrize(
    "other_minutes, expected",
    [
        (600 + 29, False),   # just inside the unsafe window after the anchor
        (600 + 30, True),    # exactly the minimum gap after
        (600, False),        # simultaneous
        (600 - 479, False),  # just inside the unsafe window before
        (600 - 480, True),   # exactly the minimum gap before
        (600 - 60, False),   # shortly before: the classic mistake
    ],
)
def test_dose_ordering_allows_only_outside_the_unsafe_window(other_minutes, expected):
    ordering = DoseOrdering(anchor="a", after_minutes=30, before_minutes=480)

    assert ordering.allows(anchor_minutes=600, other_minutes=other_minutes) is expected


@pytest.mark.parametrize("after, before", [(0, 480), (30, 0), (-1, 480)])
def test_dose_ordering_rejects_non_positive_gaps(after, before):
    with pytest.raises(ValueError):
        DoseOrdering(anchor="a", after_minutes=after, before_minutes=before)
