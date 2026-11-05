"""
Tests for services/planner.py

Covers: goal-stack ordering by severity then evidence strength, chronological output,
trace completeness (Section 6.1 — every decision must be traceable),
and behavior with no interactions at all.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.schemas import EvidenceStrength, Interaction, Medication, Severity
from services.planner import Planner


def _minutes(entry) -> int:
    return entry.scheduled_time.hour * 60 + entry.scheduled_time.minute


def test_no_interactions_all_medications_scheduled():
    meds = [
        Medication(name="Metformin", frequency_per_day=2),
        Medication(name="Lisinopril", frequency_per_day=1),
    ]
    plan = Planner(meds).build_plan()

    assert len(plan.entries) == 3
    assert plan.warnings == []
    assert len(plan.goal_trace) == 2  # one trace line per goal (medication)


def test_entries_are_chronologically_ordered():
    meds = [
        Medication(name="Amoxicillin", frequency_per_day=3),
        Medication(name="Atorvastatin", frequency_per_day=1),
    ]
    plan = Planner(meds).build_plan()

    times = [_minutes(e) for e in plan.entries]
    assert times == sorted(times)


def test_severe_interaction_medications_resolved_first_in_goal_trace():
    meds = [Medication(name="Warfarin", frequency_per_day=1), Medication(name="Aspirin", frequency_per_day=1)]
    interactions = [
        Interaction(
            medication_a="warfarin",
            medication_b="aspirin",
            severity=Severity.SEVERE,
            confidence=1.0,
            rule_id="RULE_TEST",
            description="Increased bleeding risk",
        )
    ]
    plan = Planner(meds, interactions).build_plan()

    # both medications are involved in the same severe interaction, so both
    # goals are popped before any unrelated mild/unknown-severity goal would be
    assert plan.goal_trace[0].startswith("goal:aspirin") or plan.goal_trace[0].startswith("goal:warfarin")
    assert "severity=severe" in plan.goal_trace[0]
    assert "severity=severe" in plan.goal_trace[1]


def _interaction(a: str, b: str, severity: Severity, evidence: EvidenceStrength) -> Interaction:
    return Interaction(
        medication_a=a,
        medication_b=b,
        severity=severity,
        evidence=evidence,
        confidence=1.0,
        rule_id="RULE_TEST",
        description="test interaction",
    )


def test_stronger_evidence_breaks_ties_within_the_same_severity():
    meds = [
        Medication(name="Atorvastatin", frequency_per_day=1),
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Ibuprofen", frequency_per_day=1),
        Medication(name="Lisinopril", frequency_per_day=1),
    ]
    interactions = [
        _interaction("atorvastatin", "warfarin", Severity.MODERATE, EvidenceStrength.LIMITED),
        _interaction("ibuprofen", "lisinopril", Severity.MODERATE, EvidenceStrength.STRONG),
    ]
    plan = Planner(meds, interactions).build_plan()

    names = [line.split()[0] for line in plan.goal_trace]
    # same severity, so the well-documented pair goes first (ties then by name)
    assert names == ["goal:ibuprofen", "goal:lisinopril", "goal:atorvastatin", "goal:warfarin"]


def test_severity_outranks_evidence_strength():
    meds = [
        Medication(name="Aspirin", frequency_per_day=1),
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Metoprolol", frequency_per_day=1),
        Medication(name="Ibuprofen", frequency_per_day=1),
    ]
    interactions = [
        _interaction("aspirin", "warfarin", Severity.SEVERE, EvidenceStrength.LIMITED),
        _interaction("metoprolol", "ibuprofen", Severity.MILD, EvidenceStrength.STRONG),
    ]
    plan = Planner(meds, interactions).build_plan()

    names = [line.split()[0] for line in plan.goal_trace]
    assert set(names[:2]) == {"goal:aspirin", "goal:warfarin"}


def test_goal_trace_records_severity_and_evidence():
    meds = [Medication(name="Warfarin", frequency_per_day=1), Medication(name="Aspirin", frequency_per_day=1)]
    interactions = [_interaction("warfarin", "aspirin", Severity.SEVERE, EvidenceStrength.STRONG)]
    plan = Planner(meds, interactions).build_plan()

    assert all("severity=severe, evidence=strong" in line for line in plan.goal_trace)


def test_uninvolved_medication_traces_unknown_severity_and_evidence():
    plan = Planner([Medication(name="Metformin", frequency_per_day=1)]).build_plan()

    assert "severity=unknown, evidence=unknown" in plan.goal_trace[0]


def test_unknown_severity_medications_resolved_after_flagged_ones():
    meds = [
        Medication(name="Metformin", frequency_per_day=1),   # no interaction -> UNKNOWN
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Aspirin", frequency_per_day=1),
    ]
    interactions = [
        Interaction(
            medication_a="warfarin",
            medication_b="aspirin",
            severity=Severity.SEVERE,
            confidence=1.0,
            rule_id="RULE_TEST",
            description="Increased bleeding risk",
        )
    ]
    plan = Planner(meds, interactions).build_plan()

    metformin_index = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:metformin"))
    warfarin_index = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:warfarin"))
    aspirin_index = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:aspirin"))

    assert warfarin_index < metformin_index
    assert aspirin_index < metformin_index


def test_warnings_carry_through_to_plan():
    meds = [Medication(name="Warfarin", frequency_per_day=1), Medication(name="Aspirin", frequency_per_day=1)]
    interactions = [
        Interaction(
            medication_a="warfarin",
            medication_b="aspirin",
            severity=Severity.SEVERE,
            confidence=1.0,
            rule_id="RULE_TEST",
            description="Increased bleeding risk",
        )
    ]
    plan = Planner(meds, interactions).build_plan()

    assert plan.warnings == interactions