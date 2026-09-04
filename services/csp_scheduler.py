"""
Constraint Satisfaction Problem (CSP) scheduler for dose timing.

Models daily medication scheduling as a CSP (Section 4.1 / syllabus Unit 2):
each dose is a variable, its domain is the set of feasible time-slots for
that dose, and constraints encode same-medication spacing, meal/sleep
windows and interaction-driven separation. Solved via backtracking search
with forward checking -- a lightweight constraint-propagation step that
prunes remaining domains after every assignment so dead ends are caught
early instead of at the leaves.

This module has no dependency on the LLM layer (Section 4.3): it operates
purely on the typed `Medication` / `Interaction` schema objects produced
by earlier stages of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from models.exceptions import ConstraintUnsatisfiableError
from models.schemas import Interaction, Medication, ScheduleEntry, TimingPreference

# --- Scheduling window & granularity ------------------------------------

DAY_START_MINUTES = 6 * 60         # 06:00 -- earliest a dose may be scheduled
DAY_END_MINUTES = 22 * 60          # 22:00 -- latest a dose may be scheduled (protects sleep window)
SLOT_INTERVAL_MINUTES = 15         # granularity of the time grid

# --- Timing-preference windows (Medication.timing_preference) -----------

PREFERENCE_WINDOWS: dict[TimingPreference, tuple[int, int]] = {
    TimingPreference.MORNING: (6 * 60, 11 * 60),
    TimingPreference.AFTERNOON: (11 * 60, 16 * 60),
    TimingPreference.EVENING: (16 * 60, 20 * 60),
    TimingPreference.NIGHT: (20 * 60, DAY_END_MINUTES),
    TimingPreference.NO_PREFERENCE: (DAY_START_MINUTES, DAY_END_MINUTES),
}

# --- Meal windows (Medication.with_food) ---------------------------------

MEAL_TIMES_MINUTES: list[int] = [8 * 60, 13 * 60, 20 * 60]     # breakfast, lunch, dinner
WITH_FOOD_TOLERANCE_MINUTES = 45     # a with_food=True dose must fall within this of a meal
AWAY_FROM_FOOD_BUFFER_MINUTES = 60   # a with_food=False dose must fall at least this far from any meal

# --- Spacing constraints ---------------------------------------------------

MIN_INTERACTION_SEPARATION_MINUTES = 120     # separate interacting medications by >= 2h
SAME_MEDICATION_SPACING_SLACK = 0.8          # leave slack so even spacing isn't forced to one exact grid point


@dataclass(frozen=True)
class DoseVariable:
    """One CSP variable: a single dose of a single medication."""
    medication: str
    dose_index: int          # 0-based index among that medication's daily doses
    with_food: bool | None
    timing_preference: TimingPreference

    @property
    def name(self) -> str:
        return f"{self.medication}#{self.dose_index}"


Domain = list[int]  # candidate minute-offsets from midnight, on the SLOT_INTERVAL_MINUTES grid


@dataclass
class CSPResult:
    """A solved schedule: one ScheduleEntry per dose, each traceable to the
    constraints that shaped it."""
    entries: list[ScheduleEntry]


class CSPScheduler:
    """
    Encodes dose timing as a CSP and solves it with backtracking search
    plus forward checking.

    Variables: one per dose -- a twice-daily medication contributes two
        variables (e.g. metformin#0, metformin#1).
    Domains: minute-offsets on a SLOT_INTERVAL_MINUTES grid, pre-filtered
        by timing preference and meal constraints before search begins
        (node consistency).
    Constraints (checked pairwise, enforced via forward checking):
        - same-medication spacing: doses of one medication must be spread
          across the day rather than clustered together.
        - interaction separation: medication pairs flagged by the rule
          engine must have their doses separated by at least
          MIN_INTERACTION_SEPARATION_MINUTES.
    """

    def __init__(
        self,
        medications: list[Medication],
        interactions: list[Interaction] | None = None,
    ):
        self.medications = medications
        self.interacting_pairs: set[frozenset[str]] = {
            frozenset({i.medication_a.lower(), i.medication_b.lower()})
            for i in (interactions or [])
        }
        self.variables: list[DoseVariable] = self._build_variables()
        self.domains: dict[str, Domain] = {
            var.name: self._initial_domain(var) for var in self.variables
        }

    # -- setup ------------------------------------------------------------

    def _build_variables(self) -> list[DoseVariable]:
        variables: list[DoseVariable] = []
        for med in self.medications:
            for dose_index in range(med.frequency_per_day):
                variables.append(
                    DoseVariable(
                        medication=med.name.lower(),
                        dose_index=dose_index,
                        with_food=med.with_food,
                        timing_preference=med.timing_preference,
                    )
                )
        return variables

    def _initial_domain(self, var: DoseVariable) -> Domain:
        window_start, window_end = PREFERENCE_WINDOWS[var.timing_preference]
        candidates = list(range(window_start, window_end + 1, SLOT_INTERVAL_MINUTES))

        if var.with_food is True:
            candidates = [
                t for t in candidates
                if any(abs(t - meal) <= WITH_FOOD_TOLERANCE_MINUTES for meal in MEAL_TIMES_MINUTES)
            ]
        elif var.with_food is False:
            candidates = [
                t for t in candidates
                if all(abs(t - meal) >= AWAY_FROM_FOOD_BUFFER_MINUTES for meal in MEAL_TIMES_MINUTES)
            ]
        return candidates

    # -- constraint helpers -------------------------------------------------

    def _same_medication_min_gap(self, medication: str) -> int:
        """Minimum spacing (minutes) between doses of the same medication,
        derived by evenly dividing the dosing window by daily frequency."""
        dose_count = sum(1 for v in self.variables if v.medication == medication)
        if dose_count <= 1:
            return 0
        window = DAY_END_MINUTES - DAY_START_MINUTES
        return int((window / dose_count) * SAME_MEDICATION_SPACING_SLACK)

    def _min_gap_between(self, var_a: DoseVariable, var_b: DoseVariable) -> int | None:
        """Returns the required minimum gap (minutes) between two variables,
        or None if no spacing constraint applies to this pair."""
        if var_a.medication == var_b.medication:
            return self._same_medication_min_gap(var_a.medication)
        if frozenset({var_a.medication, var_b.medication}) in self.interacting_pairs:
            return MIN_INTERACTION_SEPARATION_MINUTES
        return None

    def _consistent(self, var: DoseVariable, value: int, assignment: dict[str, int]) -> bool:
        by_name = {v.name: v for v in self.variables}
        for other_name, other_value in assignment.items():
            other_var = by_name[other_name]
            min_gap = self._min_gap_between(var, other_var)
            if min_gap is not None and abs(value - other_value) < min_gap:
                return False
        return True

    # -- search: backtracking + forward checking -----------------------------

    def solve(self) -> CSPResult:
        assignment: dict[str, int] = {}
        domains = {name: list(dom) for name, dom in self.domains.items()}

        solution = self._backtrack(assignment, domains)
        if solution is None:
            empty = [name for name, dom in domains.items() if not dom]
            raise ConstraintUnsatisfiableError(empty or [v.name for v in self.variables])
        return self._build_result(solution)

    def _select_unassigned_variable(
        self, assignment: dict[str, int], domains: dict[str, Domain]
    ) -> DoseVariable:
        # MRV heuristic: pick the variable with the fewest remaining legal values,
        # so the search fails fast on the most constrained doses first.
        unassigned = [v for v in self.variables if v.name not in assignment]
        return min(unassigned, key=lambda v: len(domains[v.name]))

    def _backtrack(
        self, assignment: dict[str, int], domains: dict[str, Domain]
    ) -> dict[str, int] | None:
        if len(assignment) == len(self.variables):
            return dict(assignment)

        var = self._select_unassigned_variable(assignment, domains)

        for value in domains[var.name]:
            if not self._consistent(var, value, assignment):
                continue

            assignment[var.name] = value
            pruned_domains = self._forward_check(var, value, assignment, domains)

            if pruned_domains is not None:
                result = self._backtrack(assignment, pruned_domains)
                if result is not None:
                    return result

            del assignment[var.name]

        return None

    def _forward_check(
        self,
        var: DoseVariable,
        value: int,
        assignment: dict[str, int],
        domains: dict[str, Domain],
    ) -> dict[str, Domain] | None:
        """Prunes values from unassigned variables' domains that are now
        inconsistent with `var = value`. Returns None (signalling the caller
        to backtrack) if any domain empties out; otherwise a pruned copy."""
        new_domains = {name: list(dom) for name, dom in domains.items()}

        for other in self.variables:
            if other.name in assignment or other.name == var.name:
                continue

            min_gap = self._min_gap_between(var, other)
            if min_gap is None:
                continue

            new_domains[other.name] = [t for t in new_domains[other.name] if abs(t - value) >= min_gap]
            if not new_domains[other.name]:
                return None

        return new_domains

    # -- result assembly ----------------------------------------------------

    def _build_result(self, assignment: dict[str, int]) -> CSPResult:
        entries: list[ScheduleEntry] = []
        for var in sorted(self.variables, key=lambda v: assignment[v.name]):
            minutes = assignment[var.name]
            entries.append(
                ScheduleEntry(
                    medication=var.medication,
                    scheduled_time=time(hour=minutes // 60, minute=minutes % 60),
                    reasoning=self._explain(var),
                    constraint_ids=self._constraint_ids(var),
                )
            )
        return CSPResult(entries=entries)

    def _constraint_ids(self, var: DoseVariable) -> list[str]:
        ids = [f"timing_preference:{var.timing_preference.value}"]
        if var.with_food is not None:
            ids.append(f"with_food:{var.with_food}")
        if any(var.medication in pair for pair in self.interacting_pairs):
            ids.append("interaction_separation")
        return ids

    def _explain(self, var: DoseVariable) -> str:
        parts = [f"Dose {var.dose_index + 1} of {var.medication}"]
        if var.timing_preference != TimingPreference.NO_PREFERENCE:
            parts.append(f"placed within the {var.timing_preference.value} window")
        else:
            parts.append("placed within the default dosing window")
        if var.with_food is True:
            parts.append("kept near a meal time (with_food=True)")
        elif var.with_food is False:
            parts.append("kept away from meal times (with_food=False)")
        if any(var.medication in pair for pair in self.interacting_pairs):
            parts.append(f"spaced >= {MIN_INTERACTION_SEPARATION_MINUTES} min from an interacting medication")
        return ", ".join(parts) + "."