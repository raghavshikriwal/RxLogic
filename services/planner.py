"""
Goal-stack planner: assembles the final daily schedule from CSP output.

Section 6.1 requirement: every decision must be traceable, not
black-box. The planner treats each medication's dose-set as a goal,
pushes higher-risk medications onto the goal stack first (severity-
ordered), resolves them against the CSP-assigned times, and records
the resolution order in `DailyPlan.goal_trace`.

This module has no dependency on the LLM layer: it operates purely on
the typed schema objects produced by the rule engine and CSP scheduler.
"""

from __future__ import annotations

from models.schemas import DailyPlan, EvidenceStrength, Interaction, Medication, ScheduleEntry, Severity
from services.csp_scheduler import CSPScheduler

# Severity ranking used to order the goal stack — highest risk resolved first.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.SEVERE: 0,
    Severity.MODERATE: 1,
    Severity.MILD: 2,
    Severity.UNKNOWN: 3,
}

# Evidence ranking -- the tie-breaker within one severity level: of two
# equally dangerous interactions, the better-documented one is resolved first.
_EVIDENCE_RANK: dict[EvidenceStrength, int] = {
    EvidenceStrength.STRONG: 0,
    EvidenceStrength.MODERATE: 1,
    EvidenceStrength.LIMITED: 2,
    EvidenceStrength.UNKNOWN: 3,
}

# (severity, evidence) of the most pressing interaction a medication is in.
_Risk = tuple[Severity, EvidenceStrength]
_NO_RISK: _Risk = (Severity.UNKNOWN, EvidenceStrength.UNKNOWN)


def _risk_rank(risk: _Risk) -> tuple[int, int]:
    severity, evidence = risk
    return (_SEVERITY_RANK[severity], _EVIDENCE_RANK[evidence])


class Planner:
    """
    Builds the final DailyPlan from a medication list and its flagged
    interactions.

    Goal-stack model:
        - each medication is a goal ("get medication X correctly scheduled")
        - goals are pushed in risk order -- severity first, then evidence
          strength -- so medications in the most severe, best-documented
          interactions are committed to the schedule first
        - popping a goal means resolving it against the CSP-solved schedule
          and appending its trace entry to `goal_trace`
    """

    def __init__(self, medications: list[Medication], interactions: list[Interaction] | None = None):
        self.medications = medications
        self.interactions = interactions or []

    # -- goal ordering --------------------------------------------------

    def _medication_risk(self, medication: Medication) -> _Risk:
        """The most pressing (severity, evidence) among interactions involving
        this medication -- highest severity, then strongest evidence -- or
        (UNKNOWN, UNKNOWN) if it isn't involved in any."""
        name = medication.name.lower()
        involved = [
            (i.severity, i.evidence) for i in self.interactions
            if name in (i.medication_a.lower(), i.medication_b.lower())
        ]
        if not involved:
            return _NO_RISK
        return min(involved, key=_risk_rank)

    def _build_goal_stack(self) -> list[Medication]:
        """Orders medications highest-risk-first. Ties broken by name for
        determinism (Section 6.1: reproducible traces)."""
        return sorted(
            self.medications,
            key=lambda m: (*_risk_rank(self._medication_risk(m)), m.name.lower()),
        )

    # -- resolution -------------------------------------------------------

    def build_plan(self) -> DailyPlan:
        """
        Runs the CSP scheduler once for the full medication set (spacing
        constraints are global, not per-goal), then resolves the goal
        stack against that solved schedule, recording the order goals
        were popped in.
        """
        goal_stack = self._build_goal_stack()

        csp_result = CSPScheduler(self.medications, self.interactions).solve()
        entries_by_medication: dict[str, list[ScheduleEntry]] = {}
        for entry in csp_result.entries:
            entries_by_medication.setdefault(entry.medication, []).append(entry)

        goal_trace: list[str] = []
        ordered_entries: list[ScheduleEntry] = []

        for medication in goal_stack:
            name = medication.name.lower()
            severity, evidence = self._medication_risk(medication)
            goal_trace.append(
                f"goal:{name} (severity={severity.value}, evidence={evidence.value}) resolved -> "
                f"{len(entries_by_medication.get(name, []))} dose(s) committed"
            )
            ordered_entries.extend(entries_by_medication.get(name, []))

        chronological_entries = sorted(
            ordered_entries, key=lambda e: (e.scheduled_time.hour, e.scheduled_time.minute)
        )

        return DailyPlan(
            entries=chronological_entries,
            warnings=list(self.interactions),
            goal_trace=goal_trace,
        )