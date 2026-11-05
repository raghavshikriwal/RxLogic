"""
Tests for services/reasoning_service.py

Covers: end-to-end wiring (rule engine -> planner -> CSP), the
fail-safe empty-input path, and that interactions detected by the
rule engine actually flow through into the final plan's warnings.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from models.exceptions import InsufficientDataError, UnknownMedicationError
from models.schemas import Medication, Severity
from services.reasoning_service import ReasoningService, generate_daily_plan


def test_empty_medication_list_raises_insufficient_data_error():
    with pytest.raises(InsufficientDataError):
        ReasoningService().generate_daily_plan([])


def test_module_level_wrapper_matches_class_behavior():
    meds = [Medication(name="Metformin", frequency_per_day=1)]
    plan_a = generate_daily_plan(meds)
    plan_b = ReasoningService().generate_daily_plan(meds)

    assert len(plan_a.entries) == len(plan_b.entries) == 1
    assert plan_a.entries[0].medication == plan_b.entries[0].medication


def test_no_interactions_produces_plan_with_no_warnings():
    # metformin + lisinopril used to be interaction-free, but the knowledge
    # base has since grown a curated mild rule for that exact pair (see
    # test_rule_engine.py::test_real_knowledge_base_covers_expanded_curated_pairs
    # [lisinopril-metformin]). metformin + atorvastatin has no rule between
    # them in knowledge/interaction_rules.json, so it's a genuine no-warnings case.
    meds = [
        Medication(name="Metformin", frequency_per_day=2),
        Medication(name="Atorvastatin", frequency_per_day=1),
    ]
    plan = generate_daily_plan(meds)

    assert len(plan.entries) == 3
    assert plan.warnings == []
    assert len(plan.goal_trace) == 2


def test_known_interacting_pair_flows_through_to_plan_warnings():
    # warfarin + aspirin is expected to be a curated rule in
    # knowledge/interaction_rules.json (severe bleeding-risk interaction).
    meds = [
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Aspirin", frequency_per_day=1),
    ]
    plan = generate_daily_plan(meds)

    assert len(plan.warnings) >= 1
    warning = plan.warnings[0]
    assert {warning.medication_a, warning.medication_b} == {"warfarin", "aspirin"}
    assert warning.severity == Severity.SEVERE
    assert warning.rule_id  # traceable back to the source rule


def test_severe_interaction_goals_resolved_before_unrelated_medication():
    meds = [
        Medication(name="Metformin", frequency_per_day=1),  # unrelated -> UNKNOWN severity
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Aspirin", frequency_per_day=1),
    ]
    plan = generate_daily_plan(meds)

    metformin_index = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:metformin"))
    warfarin_index = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:warfarin"))
    aspirin_index = next(i for i, line in enumerate(plan.goal_trace) if line.startswith("goal:aspirin"))

    assert warfarin_index < metformin_index
    assert aspirin_index < metformin_index


def test_custom_rule_engine_can_be_injected():
    from services.rule_engine import RuleEngine

    class _EmptyRuleEngine(RuleEngine):
        def __init__(self):
            self.rules = []  # skip loading the real knowledge base
            self.known_medications = frozenset({"warfarin", "aspirin"})

    meds = [Medication(name="Warfarin", frequency_per_day=1), Medication(name="Aspirin", frequency_per_day=1)]
    plan = ReasoningService(rule_engine=_EmptyRuleEngine()).generate_daily_plan(meds)

    assert plan.warnings == []  # injected engine has no rules, so nothing fires


# ---------------------------------------------------------------------------
# Fail-safe: unknown medications must never read as "no interactions"
# ---------------------------------------------------------------------------

def test_unknown_medication_raises_unknown_medication_error():
    with pytest.raises(UnknownMedicationError) as exc_info:
        generate_daily_plan([Medication(name="Zolpidem", frequency_per_day=1)])

    assert exc_info.value.medication_names == ("Zolpidem",)


def test_unknown_medication_among_known_ones_is_not_silently_dropped():
    meds = [
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Zolpidem", frequency_per_day=1),
    ]

    with pytest.raises(UnknownMedicationError) as exc_info:
        generate_daily_plan(meds)

    assert exc_info.value.medication_name == "Zolpidem"


def test_all_unknown_medications_are_reported_together():
    meds = [
        Medication(name="Zolpidem"),
        Medication(name="Warfarin"),
        Medication(name="Xanax"),
    ]

    with pytest.raises(UnknownMedicationError) as exc_info:
        generate_daily_plan(meds)

    assert exc_info.value.medication_names == ("Zolpidem", "Xanax")


def test_known_medication_lookup_is_case_insensitive():
    plan = generate_daily_plan([Medication(name="WARFARIN"), Medication(name="aspirin")])

    assert len(plan.warnings) >= 1


def test_empty_list_still_raises_insufficient_data_before_coverage_check():
    with pytest.raises(InsufficientDataError):
        generate_daily_plan([])


# ---------------------------------------------------------------------------
# Coverage summary on every plan
# ---------------------------------------------------------------------------

def test_plan_reports_full_coverage_for_known_medications():
    meds = [
        Medication(name="Warfarin", frequency_per_day=1),
        Medication(name="Aspirin", frequency_per_day=1),
        Medication(name="Metformin", frequency_per_day=1),
    ]
    plan = generate_daily_plan(meds)

    assert plan.coverage is not None
    assert plan.coverage.is_complete
    assert plan.coverage.summary == "3 of 3 drugs checked"


def test_coverage_counts_distinct_drugs_when_one_is_listed_twice():
    meds = [
        Medication(name="Metformin", frequency_per_day=1),
        Medication(name="metformin", frequency_per_day=1),
    ]

    assert generate_daily_plan(meds).coverage.summary == "1 of 1 drug checked"


def test_duplicate_entries_are_merged_into_one_medication_with_summed_doses():
    meds = [
        Medication(name="Metformin", frequency_per_day=1),
        Medication(name="metformin", frequency_per_day=1),
    ]

    plan = generate_daily_plan(meds)

    assert [e.medication for e in plan.entries] == ["metformin", "metformin"]
