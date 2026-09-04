"""
Fuzzy-logic uncertainty layer (Layer 3, Section 4.1).

Real drug interactions are rarely binary. The rule engine flags a pair
as mild/moderate/severe based on a curated rule match, but that says
nothing about how much to trust the flag -- a severe interaction from
a well-documented openFDA source is not the same certainty as one from
a single literature note, and a patient on many concurrent medications
has a higher chance of untested/unmodeled interactions the rule engine
simply has no rule for.

This module refines each Interaction's `confidence` field using a
Mamdani fuzzy inference system over two inputs (severity, source
reliability) and a separate polypharmacy penalty, rather than
collapsing everything to a hardcoded 1.0. It never changes `severity`
itself -- that stays traceable to the exact rule that fired
(Section 6.1); only the confidence estimate is adjusted.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

from models.schemas import Interaction, Severity

# -- crisp -> fuzzy input mappings -------------------------------------------

SEVERITY_BASE_SCORE: dict[Severity, float] = {
    Severity.MILD: 0.3,
    Severity.MODERATE: 0.6,
    Severity.SEVERE: 0.9,
    Severity.UNKNOWN: 0.1,
}

# Curated rule sources, ranked by how strong the underlying evidence is.
# Falls back to 0.5 (medium) for any source string not recognized here.
SOURCE_RELIABILITY_SCORE: dict[str, float] = {
    "openFDA label / clinical literature": 0.9,
    "clinical literature": 0.6,
    "RxNav/openFDA": 0.85,
}
DEFAULT_SOURCE_RELIABILITY = 0.5

# Polypharmacy penalty: beyond this many concurrent medications, confidence
# in *completeness* (not correctness) of the flagged interactions starts to
# taper off, since combinatorial coverage of a curated rule set is finite.
POLYPHARMACY_THRESHOLD = 4
POLYPHARMACY_PENALTY_PER_EXTRA_MED = 0.03
MIN_CONFIDENCE_FLOOR = 0.05


class UncertaintyLayer:
    """
    Mamdani fuzzy inference system estimating interaction confidence
    from (severity, source reliability), with a polypharmacy penalty
    applied afterward.

    Inputs:
        severity_score     [0, 1] -- derived from the rule-flagged Severity
        source_reliability [0, 1] -- derived from the rule's cited source
    Output:
        confidence          [0, 1] -- refined trust estimate for this
                                       specific flagged interaction
    """

    def __init__(self):
        self._system = self._build_control_system()

    # -- fuzzy system construction -------------------------------------------

    def _build_control_system(self) -> ctrl.ControlSystem:
        severity = ctrl.Antecedent(np.linspace(0, 1, 101), "severity")
        reliability = ctrl.Antecedent(np.linspace(0, 1, 101), "reliability")
        confidence = ctrl.Consequent(np.linspace(0, 1, 101), "confidence")

        for var in (severity, reliability, confidence):
            var["low"] = fuzz.trimf(var.universe, [0.0, 0.0, 0.5])
            var["medium"] = fuzz.trimf(var.universe, [0.2, 0.5, 0.8])
            var["high"] = fuzz.trimf(var.universe, [0.5, 1.0, 1.0])

        rules = [
            ctrl.Rule(severity["high"] & reliability["high"], confidence["high"]),
            ctrl.Rule(severity["high"] & reliability["medium"], confidence["high"]),
            ctrl.Rule(severity["high"] & reliability["low"], confidence["medium"]),
            ctrl.Rule(severity["medium"] & reliability["high"], confidence["high"]),
            ctrl.Rule(severity["medium"] & reliability["medium"], confidence["medium"]),
            ctrl.Rule(severity["medium"] & reliability["low"], confidence["low"]),
            ctrl.Rule(severity["low"] & reliability["high"], confidence["medium"]),
            ctrl.Rule(severity["low"] & reliability["medium"], confidence["low"]),
            ctrl.Rule(severity["low"] & reliability["low"], confidence["low"]),
        ]
        return ctrl.ControlSystem(rules)

    def _fuzzy_confidence(self, severity_score: float, reliability_score: float) -> float:
        sim = ctrl.ControlSystemSimulation(self._system)
        sim.input["severity"] = severity_score
        sim.input["reliability"] = reliability_score
        sim.compute()
        return float(sim.output["confidence"])

    # -- crisp helpers --------------------------------------------------------

    def _source_reliability(self, source: str) -> float:
        return SOURCE_RELIABILITY_SCORE.get(source, DEFAULT_SOURCE_RELIABILITY)

    def _polypharmacy_penalty(self, total_medication_count: int) -> float:
        extra = max(0, total_medication_count - POLYPHARMACY_THRESHOLD)
        return extra * POLYPHARMACY_PENALTY_PER_EXTRA_MED

    # -- public API -------------------------------------------------------------

    def refine(self, interactions: list[Interaction], total_medication_count: int) -> list[Interaction]:
        """
        Returns new Interaction objects with `confidence` replaced by the
        fuzzy-refined estimate. `severity` and every other field are left
        untouched -- only the confidence estimate changes.
        """
        penalty = self._polypharmacy_penalty(total_medication_count)
        refined: list[Interaction] = []

        for interaction in interactions:
            severity_score = SEVERITY_BASE_SCORE[interaction.severity]
            reliability_score = self._source_reliability(interaction.source)

            raw_confidence = self._fuzzy_confidence(severity_score, reliability_score)
            final_confidence = max(MIN_CONFIDENCE_FLOOR, min(1.0, raw_confidence - penalty))

            refined.append(replace(interaction, confidence=round(final_confidence, 3)))

        return refined


def refine_confidence(interactions: list[Interaction], total_medication_count: int) -> list[Interaction]:
    """Module-level convenience wrapper, mirroring the pattern in
    reasoning_service.py and llm_parser.py."""
    return UncertaintyLayer().refine(interactions, total_medication_count)