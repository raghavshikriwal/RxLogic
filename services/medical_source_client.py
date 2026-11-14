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
import xml.etree.ElementTree as ET

from services.evidence_ingestion import EvidenceMetadata, IngestionResult, ingest_json_document
from pathlib import Path

RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_LABEL_URL = "https://api.fda.gov/drug/label.json"
DAILYMED_SPL_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"

DEFAULT_TIMEOUT_SECONDS = 12
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_OPENFDA_RESULTS = 100
MAX_DAILYMED_PAGE_SIZE = 100
DAILYMED_SPL_DOCUMENT_URL = "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}.xml"
MAX_DAILYMED_LABELS_TO_STAGE = 5


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

    @staticmethod
    def _parse_dailymed_spl(xml_bytes: bytes) -> dict[str, Any]:
        """Extract verbatim SPL section text while retaining code/title locators."""
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as exc:
            raise ValueError("DailyMed returned malformed SPL XML") from exc

        def local(tag: str) -> str:
            return tag.rsplit("}", 1)[-1]

        def descendants_text(node: ET.Element) -> str:
            return " ".join(part.strip() for part in node.itertext() if part and part.strip())

        title = ""
        for node in root.iter():
            if local(node.tag) == "title":
                title = descendants_text(node)
                if title:
                    break
        sections = []
        for node in root.iter():
            if local(node.tag) != "section":
                continue
            code = next((child.attrib.get("code") for child in node if local(child.tag) == "code"), None)
            display = next((child.attrib.get("displayName") for child in node if local(child.tag) == "code"), None)
            section_title = next((descendants_text(child) for child in node if local(child.tag) == "title"), "")
            text_node = next((child for child in node if local(child.tag) == "text"), None)
            original_text = descendants_text(text_node) if text_node is not None else ""
            if section_title or original_text:
                sections.append({
                    "section_code": code, "section_code_system_display": display,
                    "section_title": section_title, "original_text": original_text,
                })
        return {"label_title": title, "sections": sections}

    def _fetch_dailymed_xml(self, setid: str) -> bytes:
        # SET ID is a UUID from the allowlisted DailyMed search response, not a user URL.
        import uuid
        try:
            normalized = str(uuid.UUID(str(setid)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("DailyMed returned an invalid SPL SET ID") from exc
        endpoint = DAILYMED_SPL_DOCUMENT_URL.format(setid=normalized)
        response = None
        try:
            response = self.session.get(endpoint, timeout=self.timeout, allow_redirects=False, stream=True,
                headers={"Accept": "application/xml", "User-Agent": "RxLogic-Educational-Demonstrator/1.0"})
            if 300 <= response.status_code < 400:
                raise requests.HTTPError("Redirect responses are not accepted", response=response)
            response.raise_for_status()
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > self.max_response_bytes:
                raise ValueError("DailyMed SPL response exceeds configured size limit")
            chunks, total = [], 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.max_response_bytes:
                    raise ValueError("DailyMed SPL response exceeds configured size limit")
                chunks.append(chunk)
            content = b"".join(chunks)
            if not content:
                raise ValueError("DailyMed returned an empty SPL document")
            return content
        except requests.RequestException as exc:
            from models.exceptions import ExternalAPIError
            raise ExternalAPIError("DailyMed", status_code=getattr(exc.response, "status_code", None)) from exc
        finally:
            if response is not None:
                response.close()

    def fetch_and_stage_dailymed_labels(self, medication_name: str, page_size: int = 10) -> SourceFetchResult:
        """Search DailyMed, retrieve full SPL XML, extract sections and stage each label separately.

        Every staged payload includes the exact original XML as UTF-8 text and
        verbatim section text. Records remain pending review and staged only.
        """
        name = self._validate_query(medication_name)
        if not 1 <= page_size <= MAX_DAILYMED_PAGE_SIZE:
            raise ValueError(f"page_size must be between 1 and {MAX_DAILYMED_PAGE_SIZE}")
        params = {"drug_name": name, "name_type": "both", "pagesize": min(page_size, MAX_DAILYMED_LABELS_TO_STAGE), "page": 1}
        search_payload = self._fetch_json(DAILYMED_SPL_URL, params, "DailyMed")
        rows = search_payload.get("data", [])
        if not isinstance(rows, list):
            raise ValueError("DailyMed SPL search returned an invalid data collection")
        columns = [str(c).upper() for c in search_payload.get("columns", [])] if isinstance(search_payload.get("columns"), list) else []
        staged = []
        first_label_url = None
        import json, tempfile
        from datetime import datetime, timezone
        from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
        for row in rows[:MAX_DAILYMED_LABELS_TO_STAGE]:
            if not isinstance(row, list):
                continue
            values = dict(zip(columns, row))
            setid = values.get("SETID") or values.get("SET_ID")
            if not setid:
                continue
            raw_xml = self._fetch_dailymed_xml(str(setid))
            parsed = self._parse_dailymed_spl(raw_xml)
            published = values.get("PUBLISHED_DATE")
            label_title = str(values.get("TITLE") or parsed.get("label_title") or f"DailyMed SPL {setid}")
            payload = {
                "schema": "rxlogic.dailymed_spl_candidate.v1",
                "medication_query": name, "set_id": str(setid),
                "spl_version": values.get("SPL_VERSION"),
                "published_date": published, "label_title": label_title,
                "product_identity": {"label_title": label_title, "matching_status": "needs_human_product_applicability_review"},
                "source_document": {"format": "SPL-XML", "original_xml_utf8": raw_xml.decode("utf-8", errors="replace")},
                "sections": parsed["sections"],
                "extraction": {"method": "xml_section_text_extraction", "extracted_at": datetime.now(timezone.utc).isoformat(), "clinical_interpretation_performed": False},
                "review_status": "pending_clinical_review", "promotion_status": "staged_only",
            }
            endpoint = DAILYMED_SPL_DOCUMENT_URL.format(setid=str(setid))
            if first_label_url is None:
                first_label_url = endpoint
            with tempfile.TemporaryDirectory(prefix="rxlogic-dailymed-spl-") as temp_dir:
                document = Path(temp_dir) / "spl.json"
                document.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                metadata = EvidenceMetadata(
                    publisher="U.S. National Library of Medicine DailyMed", source_type="dailymed_spl",
                    document_title=label_title, canonical_url=endpoint,
                    publication_date=self._iso_date_or_none(published), jurisdiction="US",
                )
                kwargs = {"staging_root": self.staging_root} if self.staging_root is not None else {}
                ingestion = ingest_json_document(document, metadata, **kwargs)
            staged.append(ingestion)
        # Search metadata is not treated as a clinical evidence document. Each
        # full label has its own immutable evidence artifact and locator.
        if not staged:
            return SourceFetchResult("DailyMed", name, self._query_url(DAILYMED_SPL_URL, params), 0,
                self._stage_empty_dailymed_search(name, params))
        # Backward-compatible summary result points to the first label; count
        # reports all separately staged full SPLs.
        return SourceFetchResult("DailyMed", name, str(first_label_url), len(staged), staged[0])

    @staticmethod
    def _iso_date_or_none(value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        from datetime import datetime
        for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date().isoformat()
            except ValueError:
                pass
        return None

    def _stage_empty_dailymed_search(self, name: str, params: dict[str, Any]) -> Any:
        # Preserve a bounded, auditable no-match search result without claiming
        # that the medicine has no clinical information.
        import json, tempfile
        from services.evidence_ingestion import EvidenceMetadata, ingest_json_document
        with tempfile.TemporaryDirectory(prefix="rxlogic-dailymed-empty-") as temp_dir:
            document = Path(temp_dir) / "search.json"
            document.write_text(json.dumps({"medication_query": name, "matched_labels": [], "status": "no_dailymed_label_match"}), encoding="utf-8")
            metadata = EvidenceMetadata("U.S. National Library of Medicine DailyMed", "dailymed_spl", f"DailyMed label search: {name}", self._query_url(DAILYMED_SPL_URL, params), jurisdiction="US")
            kwargs = {"staging_root": self.staging_root} if self.staging_root is not None else {}
            return ingest_json_document(document, metadata, **kwargs)

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
