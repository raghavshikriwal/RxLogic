"""
Core data models for RxLogic.

These dataclasses define the strict schema boundary between the
neural (LLM) layer and the symbolic reasoning core. All downstream
services operate only on these typed structures — never on raw
text or untyped dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import time
from typing import Optional


class Severity(str, Enum):
    """Interaction severity classification."""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"  # insufficient data — fail-safe default


class EvidenceStrength(str, Enum):
    """How well documented an interaction is, independent of how dangerous it is.

    Severity answers "how bad is it if this happens?"; evidence strength
    answers "how sure are we that it happens?". The two vary independently
    (a rare-but-fatal interaction and a well-proven-but-trivial one are
    both real), so they are never folded into one field.
    """
    STRONG = "strong"          # consistent label warnings / well-replicated clinical data
    MODERATE = "moderate"      # documented, but mixed or indirect evidence
    LIMITED = "limited"        # theoretical or thinly supported
    UNKNOWN = "unknown"        # not recorded -- fail-safe default


class NameMatch(str, Enum):
    """How a user-entered medication name was matched to a known generic."""
    EXACT = "exact"
    ALIAS = "alias"   # curated brand name or spelling variant
    FUZZY = "fuzzy"   # near-miss spelling, accepted only when unambiguous


class FoodRequirement(str, Enum):
    """What the knowledge base says about taking a drug relative to meals."""
    WITH_FOOD = "with_food"
    EMPTY_STOMACH = "empty_stomach"
    NO_RESTRICTION = "no_restriction"   # no meal constraint; any note is advice only


class FoodStatus(str, Enum):
    """What happened when a drug's food rule met the user's own input."""
    APPLIED = "applied"                         # user left it open; the rule set it
    MATCHES_INPUT = "matches_input"             # user already chose what the rule says
    CONFLICTS_WITH_INPUT = "conflicts_with_input"  # user chose the opposite; their choice is kept, but flagged
    INFORMATIONAL = "informational"             # rule is advice only (no scheduling effect)


class TimingPreference(str, Enum):
    """User's stated preference for when a dose should be taken."""
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"
    NO_PREFERENCE = "no_preference"


@dataclass(frozen=True)
class Medication:
    """A single medication entry, resolved against the knowledge base."""
    name: str
    rxcui: Optional[str] = None          # RxNav concept ID, if resolved
    dosage_mg: Optional[float] = None
    frequency_per_day: int = 1
    timing_preference: TimingPreference = TimingPreference.NO_PREFERENCE
    with_food: Optional[bool] = None     # None = unknown/unspecified


@dataclass(frozen=True)
class DoseOrdering:
    """An order-aware spacing rule for an interacting pair.

    Some interactions depend on which drug comes first. Relative to the
    `anchor` drug's dose, the other drug's dose is acceptable only if it is
    taken at least `after_minutes` later, or at least `before_minutes`
    earlier. Anything in between is the unsafe window.
    """
    anchor: str
    after_minutes: int
    before_minutes: int

    def __post_init__(self) -> None:
        if self.after_minutes <= 0 or self.before_minutes <= 0:
            raise ValueError(
                f"DoseOrdering gaps must be positive, got after={self.after_minutes}, "
                f"before={self.before_minutes}"
            )

    def allows(self, anchor_minutes: int, other_minutes: int) -> bool:
        """True if the other drug's dose time is safe relative to the anchor's."""
        delta = other_minutes - anchor_minutes
        return delta >= self.after_minutes or delta <= -self.before_minutes


@dataclass(frozen=True)
class Interaction:
    """A flagged interaction between two medications, with traceable source."""
    medication_a: str
    medication_b: str
    severity: Severity
    confidence: float                    # 0.0–1.0, from uncertainty layer
    rule_id: str                         # traces back to the firing rule
    description: str
    source: str = "RxNav/openFDA"
    evidence: EvidenceStrength = EvidenceStrength.UNKNOWN
    # Minimum minutes between doses of this pair. None = no pair-specific
    # guidance recorded, so the scheduler applies its default separation.
    separation_minutes: Optional[int] = None
    # Order-aware alternative to separation_minutes, for pairs where the
    # sequence of doses matters. None when the pair has no such rule.
    ordering: Optional[DoseOrdering] = None
    evidence_source_ids: tuple[str, ...] = ()
    review_status: str = "needs_clinical_review"
    jurisdiction: str = "unspecified"


@dataclass(frozen=True)
class ScheduleEntry:
    """A single dose placement in the final generated schedule."""
    medication: str
    scheduled_time: time
    reasoning: str                       # human-readable explanation
    constraint_ids: list[str] = field(default_factory=list)  # traces to CSP constraints

@dataclass(frozen=True)
class Coverage:
    """How much of the user's medication list the knowledge base could check.

    "No interactions flagged" only means something when every drug was
    actually checked, so every plan carries this alongside its warnings.
    `total` counts distinct drugs (case-insensitive); `unchecked` lists
    the ones the knowledge base has no data on, in input order.
    """
    total: int
    unchecked: tuple[str, ...] = ()
    identity_only: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.total < 0 or len(self.unchecked) > self.total or len(self.identity_only) > self.total:
            raise ValueError(
                f"Invalid coverage: {len(self.unchecked)} unchecked drug(s) out of {self.total} total"
            )

    @property
    def checked(self) -> int:
        return self.total - len(self.unchecked)

    @property
    def is_complete(self) -> bool:
        return not self.unchecked

    @property
    def summary(self) -> str:
        noun = "drug" if self.total == 1 else "drugs"
        return f"{self.checked} of {self.total} {noun} checked"


@dataclass(frozen=True)
class NameResolution:
    """Records that a user-entered name was mapped to a known generic, so the
    correction is shown to the user instead of being applied silently."""
    input_name: str
    canonical_name: str
    match: NameMatch
    score: float = 1.0                   # similarity; only meaningful for FUZZY


@dataclass(frozen=True)
class FoodGuidance:
    """One drug's food rule and how it was used, surfaced to the user so a
    meal constraint is never applied (or ignored) silently."""
    medication: str
    requirement: FoodRequirement
    status: FoodStatus
    note: str = ""
    source: str = ""
    rule_id: str = ""
    evidence_source_ids: tuple[str, ...] = ()
    review_status: str = "needs_clinical_review"


@dataclass(frozen=True)
class DailyPlan:
    """The planner's final output: a chronologically-ordered schedule,
    surfaced safety warnings, and a full goal-stack resolution trace
    (Section 6.1: every decision must be traceable, not black-box)."""
    entries: list[ScheduleEntry]                               # chronological, ready for display
    warnings: list[Interaction] = field(default_factory=list)  # moderate/severe interactions surfaced to the user
    goal_trace: list[str] = field(default_factory=list)        # order in which sub-goals were committed
    resolutions: list[NameResolution] = field(default_factory=list)  # brand/typo names mapped to generics
    food_guidance: list[FoodGuidance] = field(default_factory=list)  # per-drug meal rules and how each was used
    coverage: Optional[Coverage] = None                        # set by ReasoningService; None only if a plan is built outside the pipeline
    clinical_assessment: dict = field(default_factory=dict)     # evidence-governed Task 09 findings; never a diagnosis or prescription
