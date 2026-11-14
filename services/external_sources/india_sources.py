"""India source registry.

No CDSCO API or bulk-reuse contract is assumed. Until an approved official
interface is configured, this connector reports an explicit unavailable state
instead of scraping pages or fabricating results.
"""
from __future__ import annotations

from services.external_sources.base import SourceConnectorResult


class IndiaRegulatoryConnector:
    source_id = "india_regulatory"
    display_name = "India regulatory sources"

    def search_and_stage(self, medication_name: str) -> SourceConnectorResult:
        return SourceConnectorResult(
            source_id=self.source_id, display_name=self.display_name,
            status="not_configured", query=medication_name,
            message=(
                "No approved machine-readable CDSCO source connector is configured. "
                "Use verified official product documentation and ingest it through the existing review workflow."
            ),
        )
