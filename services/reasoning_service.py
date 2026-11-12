"""
Top-level reasoning service -- the single entry point into the symbolic core.

Wires together the three independent reasoning stages behind one call:
    0. FoodRules.apply()                -> fills open meal constraints from
                                            per-drug food rules
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

from dataclasses import replace
import os
from pathlib import Path

from models.exceptions import InsufficientDataError, UnknownMedicationError
from models.schemas import DailyPlan, Medication
from services.food_rules import FoodRules
from services.name_normalizer import NameNormalizer
from services.planner import Planner
from services.rule_engine import RuleEngine
from services.uncertainty import refine_confidence


def _merge_duplicate_medications(medications: list[Medication]) -> list[Medication]:
    """Collapses repeated entries for one drug (case-insensitive) into a
    single Medication whose daily frequency is the sum of its entries.

    Every downstream stage keys on the medication name, so duplicates
    must be resolved once, up front. All other fields come from the
    first entry listed. First-seen order is preserved.
    """
    grouped: dict[str, list[Medication]] = {}
    for medication in medications:
        grouped.setdefault(medication.name.lower(), []).append(medication)

    return [
        replace(entries[0], frequency_per_day=sum(m.frequency_per_day for m in entries))
        for entries in grouped.values()
    ]


class ReasoningService:
    """Orchestrates rule engine -> uncertainty refinement -> planner (-> CSP) into one call."""

    @classmethod
    def from_active_release(cls, knowledge_root: Path | None = None) -> "ReasoningService":
        """Build the service from one integrity-verified active release only."""
        rule_engine = RuleEngine.from_active_release(knowledge_root)
        food_rules = FoodRules.from_active_release(knowledge_root)
        if rule_engine.knowledge_release != food_rules.knowledge_release:
            from services.knowledge_release import KnowledgeReleaseError
            raise KnowledgeReleaseError("interaction and food knowledge releases do not match")
        return cls(rule_engine=rule_engine, food_rules=food_rules)

    def __init__(
        self,
        rule_engine: RuleEngine | None = None,
        name_normalizer: NameNormalizer | None = None,
        food_rules: FoodRules | None = None,
    ):
        # Allow injection for testing; default to the curated knowledge base.
        self.rule_engine = rule_engine or RuleEngine()
        self.name_normalizer = name_normalizer or NameNormalizer.from_file(
            self.rule_engine.medication_rxcuis
        )
        self.food_rules = food_rules or FoodRules()

    def generate_daily_plan(self, medications: list[Medication]) -> DailyPlan:
        """
        Runs the full symbolic pipeline on a resolved medication list and
        returns the final DailyPlan.

        Fail-safe (Section 9): an empty medication list has nothing to
        reason about, so this raises InsufficientDataError rather than
        returning a hollow, misleadingly "valid" plan. Likewise, any
        medication outside the knowledge base raises
        UnknownMedicationError (listing every unrecognized drug) instead
        of being scheduled as if it had no interactions.

        Brand names and near-miss spellings are first mapped to generics
        (see services.name_normalizer); each such mapping is reported in
        `plan.resolutions`. Names that cannot be mapped confidently are left
        as-is and rejected as unknown.

        Every returned plan carries a `Coverage` summary (e.g. "6 of 6
        drugs checked") so a clean warnings list is never mistaken for
        "everything was verified".
        """
        if not medications:
            raise InsufficientDataError("no medications provided to reason about")

        # Brand names and typos become generics first, so "Coumadin" and
        # "warfarin" are one drug for coverage, merging and rule matching.
        medications, resolutions = self.name_normalizer.normalize(medications)
        medications = _merge_duplicate_medications(medications)

        coverage = self.rule_engine.assess_coverage(medications)
        if not coverage.is_complete:
            raise UnknownMedicationError(*coverage.unchecked)

        # Per-drug meal rules fill in a with_food the user left open (and flag
        # conflicts with one they set), before the scheduler sees the list.
        medications, food_guidance = self.food_rules.apply(medications)

        interactions = self.rule_engine.check_interactions(medications)
        interactions = refine_confidence(interactions, total_medication_count=len(medications))
        plan = Planner(medications, interactions).build_plan()
        return replace(plan, coverage=coverage, resolutions=resolutions, food_guidance=food_guidance)


def generate_daily_plan(medications: list[Medication]) -> DailyPlan:
    """Build the configured knowledge runtime, then generate a plan.

    Runtime configuration is validated before request-level input validation,
    so an empty request cannot mask an unsafe or invalid knowledge setup.
    Active-release mode never falls back to legacy development datasets.
    """
    mode = os.getenv("RXLOGIC_KNOWLEDGE_MODE", "legacy_development").strip().lower()
    if mode == "legacy_development":
        service = ReasoningService()
    elif mode == "active_release":
        configured_root = os.getenv("RXLOGIC_KNOWLEDGE_ROOT")
        knowledge_root = Path(configured_root) if configured_root else None
        service = ReasoningService.from_active_release(knowledge_root)
    else:
        raise ValueError(
            "RXLOGIC_KNOWLEDGE_MODE must be 'legacy_development' or 'active_release'"
        )
    return service.generate_daily_plan(medications)