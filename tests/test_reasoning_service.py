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
from models.schemas import EvidenceStrength, FoodStatus, Medication, Severity
from services.csp_scheduler import AWAY_FROM_FOOD_BUFFER_MINUTES, MEAL_TIMES_MINUTES, WITH_FOOD_TOLERANCE_MINUTES
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
    assert warning.evidence == EvidenceStrength.STRONG
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
            self.medication_rxcuis = {"warfarin": "11289", "aspirin": "1191"}
            self.known_medications = frozenset(self.medication_rxcuis)

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
        Medication(name="Trazodone"),
    ]

    with pytest.raises(UnknownMedicationError) as exc_info:
        generate_daily_plan(meds)

    assert exc_info.value.medication_names == ("Zolpidem", "Trazodone")


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


# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

def test_brand_name_is_checked_instead_of_rejected_as_unknown():
    meds = [Medication(name="Coumadin"), Medication(name="Aspirin")]

    plan = generate_daily_plan(meds)

    assert plan.coverage.is_complete
    assert {plan.warnings[0].medication_a, plan.warnings[0].medication_b} == {"warfarin", "aspirin"}
    assert [(r.input_name, r.canonical_name) for r in plan.resolutions] == [("Coumadin", "warfarin")]


def test_brand_and_generic_of_one_drug_merge_into_single_drug():
    meds = [Medication(name="Coumadin", frequency_per_day=1), Medication(name="warfarin", frequency_per_day=1)]

    plan = generate_daily_plan(meds)

    assert plan.coverage.total == 1
    assert len(plan.entries) == 2  # two daily doses of one drug


def test_unresolvable_name_still_raises_unknown_medication():
    with pytest.raises(UnknownMedicationError) as exc_info:
        generate_daily_plan([Medication(name="Coumadin"), Medication(name="Zolpidem")])

    assert exc_info.value.medication_names == ("Zolpidem",)


def test_exact_names_produce_no_resolutions():
    plan = generate_daily_plan([Medication(name="Metformin")])

    assert plan.resolutions == []


# ---------------------------------------------------------------------------
# Per-drug food rules
# ---------------------------------------------------------------------------

def _minutes(entry) -> int:
    return entry.scheduled_time.hour * 60 + entry.scheduled_time.minute


def test_unreviewed_with_food_rule_does_not_force_doses_near_meals():
    plan = generate_daily_plan([Medication(name="Metformin", frequency_per_day=2)])

    assert plan.food_guidance[0].status == FoodStatus.INFORMATIONAL
    assert plan.food_guidance[0].note == "Not applied: this rule requires clinical review."


def test_empty_stomach_rule_keeps_doses_away_from_meals():
    plan = generate_daily_plan([Medication(name="Levothyroxine")])

    for entry in plan.entries:
        assert all(abs(_minutes(entry) - meal) >= AWAY_FROM_FOOD_BUFFER_MINUTES for meal in MEAL_TIMES_MINUTES)


def test_conflicting_user_choice_wins_and_is_reported():
    plan = generate_daily_plan([Medication(name="Levothyroxine", with_food=True)])

    assert any(abs(_minutes(plan.entries[0]) - meal) <= WITH_FOOD_TOLERANCE_MINUTES for meal in MEAL_TIMES_MINUTES)
    assert plan.food_guidance[0].status == FoodStatus.INFORMATIONAL
    assert plan.food_guidance[0].note == "Not applied: this rule requires clinical review."


def test_plan_without_any_food_rule_has_no_food_guidance():
    plan = generate_daily_plan([Medication(name="Aspirin")])

    assert plan.food_guidance == []


def test_reasoning_service_attaches_fail_safe_clinical_assessment():
    plan = generate_daily_plan([Medication(name="Metformin")])
    assert plan.clinical_assessment["clinical_use_permitted"] is False
    assert plan.clinical_assessment["status"] == "insufficient_approved_knowledge"
    assert plan.clinical_assessment["dosage_safety"]["patient_specific_dosing_generated"] is False
