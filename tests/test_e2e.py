"""
End-to-end test: structured Medication input -> working MVP output.

Section 8.1, Day 7: exercises the full pipeline (rule engine -> CSP
scheduler -> planner) with no mocking and no LLM layer involved,
against the real curated knowledge/interaction_rules.json. This is
the final proof the symbolic core works standalone before the LLM
interface is layered on top of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import DailyPlan, Medication, Severity, TimingPreference
from services.reasoning_service import generate_daily_plan


def _minutes(entry) -> int:
    return entry.scheduled_time.hour * 60 + entry.scheduled_time.minute


def test_full_pipeline_realistic_patient_case():
    """
    A realistic multi-condition patient: diabetes + hypertension +
    high cholesterol + on anticoagulation, self-medicating with an
    OTC NSAID -- a classic high-risk polypharmacy case that should
    exercise every stage of the pipeline at once.
    """
    medications = [
        Medication(name="Metformin", frequency_per_day=2, with_food=True),
        Medication(name="Lisinopril", frequency_per_day=1, timing_preference=TimingPreference.MORNING),
        Medication(name="Atorvastatin", frequency_per_day=1, timing_preference=TimingPreference.NIGHT),
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Ibuprofen", frequency_per_day=2, with_food=True),
    ]

    plan = generate_daily_plan(medications)

    # -- structural sanity -------------------------------------------------
    assert isinstance(plan, DailyPlan)
    expected_dose_count = sum(m.frequency_per_day for m in medications)
    assert len(plan.entries) == expected_dose_count

    # -- schedule is fully chronological ------------------------------------
    times = [_minutes(e) for e in plan.entries]
    assert times == sorted(times)

    # -- known severe interaction (warfarin+ibuprofen) must be flagged -------
    severe_warnings = [w for w in plan.warnings if w.severity == Severity.SEVERE]
    assert any({w.medication_a, w.medication_b} == {"warfarin", "ibuprofen"} for w in severe_warnings)

    # -- known moderate interaction (lisinopril+ibuprofen) must be flagged ---
    moderate_warnings = [w for w in plan.warnings if w.severity == Severity.MODERATE]
    assert any({w.medication_a, w.medication_b} == {"lisinopril", "ibuprofen"} for w in moderate_warnings)

    # -- every entry carries a human-readable, traceable reason --------------
    assert all(entry.reasoning for entry in plan.entries)
    assert all(entry.constraint_ids for entry in plan.entries)

    # -- goal-stack traceability: severe-interaction meds resolved first -----
    warfarin_idx = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:warfarin"))
    ibuprofen_idx = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:ibuprofen"))
    atorvastatin_idx = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:atorvastatin"))
    assert warfarin_idx < atorvastatin_idx
    assert ibuprofen_idx < atorvastatin_idx


def test_full_pipeline_no_interaction_case_still_produces_full_trace():
    """A clean case (no flagged interactions) should still produce a
    complete, chronological, fully-traced plan -- the fail-safe design
    must not treat 'no warnings' as 'nothing to explain'."""
    medications = [
        Medication(name="Levothyroxine", frequency_per_day=1, timing_preference=TimingPreference.MORNING),
        Medication(name="Metoprolol", frequency_per_day=2),
    ]

    plan = generate_daily_plan(medications)

    assert len(plan.entries) == 3
    assert plan.warnings == []
    assert len(plan.goal_trace) == 2
    assert all(entry.reasoning for entry in plan.entries)