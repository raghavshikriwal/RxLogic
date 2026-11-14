"""RxNorm identity connector, reusing the existing bounded RxNav client."""
from __future__ import annotations

from services.external_sources.base import SourceConnectorResult
from services.medical_source_client import MedicalSourceClient


class RxNormConnector:
    source_id = "rxnorm"
    display_name = "RxNorm / RxNav"

    def __init__(self, client: MedicalSourceClient | None = None):
        self.client = client or MedicalSourceClient()

    def search_and_stage(self, medication_name: str) -> SourceConnectorResult:
        fetched = self.client.fetch_and_stage_rxnorm_concept(medication_name)
        return SourceConnectorResult(
            source_id=self.source_id, display_name=self.display_name, status="staged",
            query=fetched.query, source_url=fetched.source_url, result_count=fetched.result_count,
            evidence_record_id=fetched.ingestion.record_id,
            review_status=fetched.ingestion.review_status,
            promotion_status=fetched.ingestion.promotion_status,
        )
