"""
Top-level reasoning service -- the single entry point into the symbolic core.

Wires together the three independent reasoning stages behind one call:
    1. RuleEngine.check_interactions()  -> flags known interaction pairs
    2. refine_confidence()              -> fuzzy-refines each interaction's
                                            confidence score (Section 4.1
                                            uncertainty layer)
    3. Planner.build_plan()             -> internally runs CSPScheduler,
                                            then goal-stack-resolves the
                                            final chronological schedule

This is the only module the API layer (Day 7) or the LLM-facing layer
should call. Neither the rule engine, the CSP scheduler, the uncertainty
layer, nor the planner should be invoked directly outside this service,
so there is exactly one place where the reasoning pipeline order is
defined (Section 4.1).
"""

from __future__ import annotations

from models.exceptions import InsufficientDataError
from models.schemas import DailyPlan, Medication
from services.planner import Planner
from services.rule_engine import RuleEngine
from services.uncertainty import refine_confidence


class ReasoningService:
    """Orchestrates rule engine -> uncertainty refinement -> planner (-> CSP) into one call."""

    def __init__(self, rule_engine: RuleEngine | None = None):
        # Allow injection for testing; default to the curated knowledge base.
        self.rule_engine = rule_engine or RuleEngine()

    def generate_daily_plan(self, medications: list[Medication]) -> DailyPlan:
        """
        Runs the full symbolic pipeline on a resolved medication list and
        returns the final DailyPlan.

        Fail-safe (Section 9): an empty medication list has nothing to
        reason about, so this raises InsufficientDataError rather than
        returning a hollow, misleadingly "valid" plan.
        """
        if not medications:
            raise InsufficientDataError("no medications provided to reason about")

        interactions = self.rule_engine.check_interactions(medications)
        interactions = refine_confidence(interactions, total_medication_count=len(medications))
        plan = Planner(medications, interactions).build_plan()
        return plan


def generate_daily_plan(medications: list[Medication]) -> DailyPlan:
    """Module-level convenience wrapper around ReasoningService, for callers
    that don't need to inject a custom RuleEngine (e.g. the API layer)."""
    return ReasoningService().generate_daily_plan(medications)