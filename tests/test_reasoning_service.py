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

from models.exceptions import InsufficientDataError
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
    meds = [
        Medication(name="Metformin", frequency_per_day=2),
        Medication(name="Lisinopril", frequency_per_day=1),
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

    meds = [Medication(name="Warfarin", frequency_per_day=1), Medication(name="Aspirin", frequency_per_day=1)]
    plan = ReasoningService(rule_engine=_EmptyRuleEngine()).generate_daily_plan(meds)

    assert plan.warnings == []  # injected engine has no rules, so nothing fires