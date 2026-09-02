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