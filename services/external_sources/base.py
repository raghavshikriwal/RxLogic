"""Shared source connector contracts and safe result types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SourceCapability:
    source_id: str
    display_name: str
    jurisdiction: str
    status: str
    description: str
    documentation_url: str


@dataclass(frozen=True)
class SourceConnectorResult:
    source_id: str
    display_name: str
    status: str
    query: str
    source_url: str | None = None
    result_count: int = 0
    evidence_record_id: str | None = None
    review_status: str | None = None
    promotion_status: str | None = None
    cached: bool = False
    message: str | None = None


class MedicationSourceConnector(Protocol):
    """A connector stages evidence; it never returns approved clinical claims."""

    source_id: str

    def search_and_stage(self, medication_name: str) -> SourceConnectorResult: ...
