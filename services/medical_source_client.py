"""
Bounded, allowlisted clients for official medication data APIs.

Fetched documents are always handed to the Task 03 evidence staging service.
They are never converted into clinical rules or exposed as medical advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from services.evidence_ingestion import EvidenceMetadata, IngestionResult, ingest_json_document
from pathlib import Path

RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
DAILYMED_SPL_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"

DEFAULT_TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_OPENFDA_RESULTS = 100
MAX_DAILYMED_PAGE_SIZE = 100


@dataclass(frozen=True)
class SourceFetchResult:
    provider: str
    query: str
    source_url: str
    result_count: int
    ingestion: IngestionResult


class MedicalSourceClient:
    """Fetch bounded JSON from fixed official APIs and stage it for review."""

    def __init__(
        self,
        staging_root: Path | None = None,
        session: requests.Session | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if max_response_bytes <= 0 or max_response_bytes > MAX_RESPONSE_BYTES:
            raise ValueError(f"max_response_bytes must be between 1 and {MAX_RESPONSE_BYTES}")
        self.staging_root = staging_root
        self.session = session or requests.Session()
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes

    @staticmethod
    def _query_url(endpoint: str, params: dict[str, Any]) -> str:
        return f"{endpoint}?{urlencode(sorted(params.items()))}"

    def _fetch_json(self, endpoint: str, params: dict[str, Any], provider: str) -> dict[str, Any]:
        response = None
        try:
            response = self.session.get(
                endpoint,
                params=params,
                timeout=self.timeout,
                allow_redirects=False,
                stream=True,
                headers={"Accept": "application/json", "User-Agent": "RxLogic-Educational-Demonstrator/1.0"},
            )
            if 300 <= response.status_code < 400:
                raise requests.HTTPError("Redirect responses are not accepted", response=response)
            response.raise_for_status()
            declared_length = response.headers.get("Content-Length")
            if declared_length and int(declared_length) > self.max_response_bytes:
                raise ValueError(f"{provider} response exceeds {self.max_response_bytes} bytes")
            chunks: list[bytes] = []
            total_bytes = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total_bytes += len(chunk)
                if total_bytes > self.max_response_bytes:
                    raise ValueError(f"{provider} response exceeds {self.max_response_bytes} bytes")
                chunks.append(chunk)
            content = b"".join(chunks)
            if not content:
                raise ValueError(f"{provider} returned an empty response")
            import json
            payload = json.loads(content.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"{provider} response must be a JSON object")
            return payload
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            from models.exceptions import ExternalAPIError
            raise ExternalAPIError(provider, status_code=status) from exc
        except (UnicodeDecodeError, ValueError) as exc:
            if isinstance(exc, ValueError) and str(exc).startswith(provider + " response"):
                raise
            raise ValueError(f"{provider} returned invalid JSON: {exc}") from exc
        finally:
            if response is not None:
                response.close()

    def _fetch_and_stage(
        self,
        *,
        provider: str,
        query: str,
        endpoint: str,
        params: dict[str, Any],
        publisher: str,
        source_type: str,
        title: str,
    ) -> SourceFetchResult:
        payload = self._fetch_json(endpoint, params, provider)
        canonical_url = self._query_url(endpoint, params)
        # Stage exactly the JSON response. The staging service enforces the
        # approved host allowlist, size limit, hash and review-only status.
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory(prefix="rxlogic-source-") as temp_dir:
            document = Path(temp_dir) / "response.json"
            document.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            metadata = EvidenceMetadata(
                publisher=publisher,
                source_type=source_type,
                document_title=title,
                canonical_url=canonical_url,
                jurisdiction="US",
            )
            kwargs = {"staging_root": self.staging_root} if self.staging_root is not None else {}
            ingestion = ingest_json_document(document, metadata, **kwargs)

        if provider == "RxNav":
            ids = payload.get("idGroup", {}).get("rxnormId", [])
            count = len(ids) if isinstance(ids, list) else 0
        elif provider == "openFDA":
            results = payload.get("results", [])
            count = len(results) if isinstance(results, list) else 0
        else:
            data = payload.get("data", [])
            count = len(data) if isinstance(data, list) else 0

        return SourceFetchResult(
            provider=provider,
            query=query,
            source_url=canonical_url,
            result_count=count,
            ingestion=ingestion,
        )

    def fetch_and_stage_rxnorm_concept(self, medication_name: str) -> SourceFetchResult:
        name = self._validate_query(medication_name)
        params = {"name": name}
        return self._fetch_and_stage(
            provider="RxNav",
            query=name,
            endpoint=f"{RXNAV_BASE_URL}/rxcui.json",
            params=params,
            publisher="U.S. National Library of Medicine",
            source_type="rxnorm_concept",
            title=f"RxNorm concept lookup: {name}",
        )

    def fetch_and_stage_openfda_label(self, medication_name: str, limit: int = 5) -> SourceFetchResult:
        name = self._validate_query(medication_name)
        if not 1 <= limit <= MAX_OPENFDA_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_OPENFDA_RESULTS}")
        params = {"search": f'openfda.generic_name:"{name}"', "limit": limit}
        return self._fetch_and_stage(
            provider="openFDA",
            query=name,
            endpoint=OPENFDA_LABEL_URL,
            params=params,
            publisher="U.S. Food and Drug Administration",
            source_type="fda_label",
            title=f"openFDA drug label search: {name}",
        )

    def fetch_and_stage_dailymed_labels(self, medication_name: str, page_size: int = 10) -> SourceFetchResult:
        name = self._validate_query(medication_name)
        if not 1 <= page_size <= MAX_DAILYMED_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_DAILYMED_PAGE_SIZE}")
        params = {"drug_name": name, "name_type": "both", "pagesize": page_size, "page": 1}
        return self._fetch_and_stage(
            provider="DailyMed",
            query=name,
            endpoint=DAILYMED_SPL_URL,
            params=params,
            publisher="U.S. National Library of Medicine DailyMed",
            source_type="dailymed_spl",
            title=f"DailyMed SPL search: {name}",
        )

    @staticmethod
    def _validate_query(value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("medication_name must be a string")
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200:
            raise ValueError("medication_name must contain 1 to 200 characters")
        if any(ord(char) < 32 for char in cleaned):
            raise ValueError("medication_name must not contain control characters")
        return cleaned
