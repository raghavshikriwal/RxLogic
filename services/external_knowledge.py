"""Task 16 external medication evidence retrieval orchestration.

Searches are explicit user actions. Successful source responses are staged by
MedicalSourceClient into the existing immutable, review-only evidence store.
A small per-process TTL cache suppresses repeated upstream calls; it is an
optimization only and does not change evidence status or approval.
"""
from __future__ import annotations

import threading
import time
from dataclasses import asdict
from typing import Callable

from services.external_sources.base import SourceConnectorResult
from services.external_sources.dailymed import DailyMedConnector
from services.external_sources.india_sources import IndiaRegulatoryConnector
from services.external_sources.openfda import OpenFDAConnector
from services.external_sources.registry import available_source_capabilities
from services.external_sources.rxnorm import RxNormConnector
from services.medical_source_client import MedicalSourceClient

ALLOWED_SOURCES = frozenset({"rxnorm", "dailymed", "openfda", "india_regulatory"})
DEFAULT_SOURCES = ("rxnorm", "dailymed", "openfda", "india_regulatory")
CACHE_TTL_SECONDS = 15 * 60


class ExternalKnowledgeService:
    def __init__(self, client: MedicalSourceClient | None = None, *, cache_ttl: int = CACHE_TTL_SECONDS, clock: Callable[[], float] = time.monotonic):
        self.client = client or MedicalSourceClient()
        self.cache_ttl = max(0, int(cache_ttl))
        self.clock = clock
        self._cache: dict[tuple[str, str], tuple[float, SourceConnectorResult]] = {}
        self._lock = threading.Lock()
        self._connectors = {
            "rxnorm": RxNormConnector(self.client),
            "dailymed": DailyMedConnector(self.client),
            "openfda": OpenFDAConnector(self.client),
            "india_regulatory": IndiaRegulatoryConnector(),
        }

    @staticmethod
    def validate_query(value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("medication_name must be a string")
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200 or any(ord(c) < 32 for c in cleaned):
            raise ValueError("medication_name must contain 1 to 200 printable characters")
        return cleaned

    def search(self, medication_name: object, sources: list[str] | None = None, *, refresh: bool = False) -> dict:
        name = self.validate_query(medication_name)
        selected = tuple(dict.fromkeys(DEFAULT_SOURCES if sources is None else sources))
        if not selected or len(selected) > len(ALLOWED_SOURCES) or any(source not in ALLOWED_SOURCES for source in selected):
            raise ValueError("sources must contain supported source identifiers")
        results: list[SourceConnectorResult] = []
        for source in selected:
            key = (name.casefold(), source)
            now = self.clock()
            with self._lock:
                cached = self._cache.get(key)
                if not refresh and cached and now - cached[0] < self.cache_ttl:
                    results.append(SourceConnectorResult(**{**asdict(cached[1]), "cached": True}))
                    continue
            try:
                result = self._connectors[source].search_and_stage(name)
            except Exception as exc:
                # Do not leak provider response bodies, local paths, or internals.
                result = SourceConnectorResult(
                    source_id=source, display_name=source, status="unavailable", query=name,
                    message=f"Source retrieval failed ({type(exc).__name__}). Try again later.",
                )
            with self._lock:
                self._cache[key] = (self.clock(), result)
            results.append(result)
        return {
            "medication_query": name,
            "results": [asdict(item) for item in results],
            "governance": {
                "all_retrieved_records_are_unapproved": True,
                "review_status": "pending_clinical_review",
                "promotion_status": "staged_only",
                "message": "Retrieved source snapshots are candidates for human review only. They are not approved clinical findings and are not used by the runtime reasoning engine.",
            },
            "source_capabilities": available_source_capabilities(),
        }
