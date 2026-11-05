"""Tests for models/schemas.py -- the Coverage value object."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.schemas import Coverage, DailyPlan


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
