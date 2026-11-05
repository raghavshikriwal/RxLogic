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


class NameMatch(str, Enum):
    """How a user-entered medication name was matched to a known generic."""
    EXACT = "exact"
    ALIAS = "alias"   # curated brand name or spelling variant
    FUZZY = "fuzzy"   # near-miss spelling, accepted only when unambiguous


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
class Interaction:
    """A flagged interaction between two medications, with traceable source."""
    medication_a: str
    medication_b: str
    severity: Severity
    confidence: float                    # 0.0–1.0, from uncertainty layer
    rule_id: str                         # traces back to the firing rule
    description: str
    source: str = "RxNav/openFDA"


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

    def __post_init__(self) -> None:
        if self.total < 0 or len(self.unchecked) > self.total:
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
class DailyPlan:
    """The planner's final output: a chronologically-ordered schedule,
    surfaced safety warnings, and a full goal-stack resolution trace
    (Section 6.1: every decision must be traceable, not black-box)."""
    entries: list[ScheduleEntry]                               # chronological, ready for display
    warnings: list[Interaction] = field(default_factory=list)  # moderate/severe interactions surfaced to the user
    goal_trace: list[str] = field(default_factory=list)        # order in which sub-goals were committed
    resolutions: list[NameResolution] = field(default_factory=list)  # brand/typo names mapped to generics
    coverage: Optional[Coverage] = None                        # set by ReasoningService; None only if a plan is built outside the pipeline
