from __future__ import annotations

from dataclasses import dataclass

import pytest

from services.external_knowledge import ExternalKnowledgeService
from services.external_sources.base import SourceConnectorResult


@dataclass
class FakeIngestion:
    record_id: str = "EVD-TEST"
    review_status: str = "pending_clinical_review"
    promotion_status: str = "staged_only"


@dataclass
class FakeFetch:
    provider: str
    query: str
    source_url: str
    result_count: int
    ingestion: FakeIngestion


class FakeClient:
    def __init__(self):
        self.calls = []

    def fetch_and_stage_rxnorm_concept(self, name):
        self.calls.append(("rxnorm", name))
        return FakeFetch("RxNav", name, "https://rxnav.nlm.nih.gov/REST/rxcui.json?name=test", 1, FakeIngestion("EVD-RX"))

    def fetch_and_stage_dailymed_labels(self, name):
        self.calls.append(("dailymed", name))
        return FakeFetch("DailyMed", name, "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json", 2, FakeIngestion("EVD-DM"))

    def fetch_and_stage_openfda_label(self, name):
        self.calls.append(("openfda", name))
        return FakeFetch("openFDA", name, "https://api.fda.gov/drug/label.json", 3, FakeIngestion("EVD-FDA"))


def test_external_search_stages_only_and_includes_india_not_configured():
    client = FakeClient()
    service = ExternalKnowledgeService(client=client)
    result = service.search("paracetamol")
    by_source = {item["source_id"]: item for item in result["results"]}
    assert by_source["rxnorm"]["evidence_record_id"] == "EVD-RX"
    assert by_source["dailymed"]["promotion_status"] == "staged_only"
    assert by_source["openfda"]["review_status"] == "pending_clinical_review"
    assert by_source["india_regulatory"]["status"] == "not_configured"
    assert result["governance"]["all_retrieved_records_are_unapproved"] is True
    assert len(client.calls) == 3


def test_external_search_uses_ttl_cache_and_refresh_bypasses_it():
    client = FakeClient()
    now = [100.0]
    service = ExternalKnowledgeService(client=client, cache_ttl=30, clock=lambda: now[0])
    first = service.search("aspirin", ["rxnorm"])
    second = service.search("ASPIRIN", ["rxnorm"])
    assert second["results"][0]["cached"] is True
    assert len(client.calls) == 1
    service.search("aspirin", ["rxnorm"], refresh=True)
    assert len(client.calls) == 2
    now[0] += 31
    service.search("aspirin", ["rxnorm"])
    assert len(client.calls) == 3


def test_external_search_rejects_bad_queries_and_sources():
    service = ExternalKnowledgeService(client=FakeClient())
    with pytest.raises(ValueError):
        service.search("  ")
    with pytest.raises(ValueError):
        service.search("aspirin", ["unknown-provider"])
    with pytest.raises(ValueError):
        service.search("x" * 201)


def test_connector_failure_is_sanitized_and_does_not_break_other_sources():
    client = FakeClient()
    client.fetch_and_stage_openfda_label = lambda name: (_ for _ in ()).throw(RuntimeError("secret local path"))
    result = ExternalKnowledgeService(client=client).search("aspirin", ["openfda"])
    assert result["results"][0]["status"] == "unavailable"
    assert "secret local path" not in result["results"][0]["message"]


def test_empty_source_list_is_rejected_instead_of_falling_back_to_every_source():
    service = ExternalKnowledgeService(client=FakeClient())
    with pytest.raises(ValueError):
        service.search("aspirin", [])


def test_medlineplus_reference_url_requires_numeric_rxcui():
    from services.external_sources.medlineplus import medication_reference_url
    from urllib.parse import urlparse, parse_qs
    url = medication_reference_url("161")
    query = parse_qs(urlparse(url).query)
    assert url.startswith("https://connect.medlineplus.gov/service?")
    assert query["mainSearchCriteria.v.c"] == ["161"]
    with pytest.raises(ValueError):
        medication_reference_url("161/../../other")


def test_source_registry_discloses_jurisdiction_and_unconfigured_india_source():
    from services.external_sources.registry import available_source_capabilities
    sources = {item["source_id"]: item for item in available_source_capabilities()}
    assert sources["rxnorm"]["jurisdiction"] == "US"
    assert sources["dailymed"]["status"] == "available"
    assert sources["india_regulatory"]["jurisdiction"] == "IN"
    assert sources["india_regulatory"]["status"] == "not_configured"


def test_dailymed_spl_parser_preserves_verbatim_section_text_and_locators():
    from services.medical_source_client import MedicalSourceClient

    xml = b'''<?xml version="1.0"?><document xmlns="urn:hl7-org:v3"><title>Example product label</title><component><structuredBody><component><section><code code="34067-9" displayName="INDICATIONS AND USAGE"/><title>INDICATIONS AND USAGE</title><text>For the treatment of example condition.</text></section><section><code code="34068-7" displayName="DOSAGE AND ADMINISTRATION"/><title>DOSAGE AND ADMINISTRATION</title><text>See full prescribing information.</text></section></component></structuredBody></component></document>'''
    parsed = MedicalSourceClient._parse_dailymed_spl(xml)
    assert parsed["label_title"] == "Example product label"
    assert len(parsed["sections"]) == 2
    assert parsed["sections"][0]["section_code"] == "34067-9"
    assert parsed["sections"][0]["section_title"] == "INDICATIONS AND USAGE"
    assert parsed["sections"][0]["original_text"] == "For the treatment of example condition."


def test_dailymed_spl_parser_rejects_malformed_xml():
    from services.medical_source_client import MedicalSourceClient
    with pytest.raises(ValueError, match="malformed SPL XML"):
        MedicalSourceClient._parse_dailymed_spl(b"<document><section>")


def test_dailymed_spl_parser_handles_namespaced_nested_text():
    from services.medical_source_client import MedicalSourceClient
    xml = b'''<document xmlns="urn:hl7-org:v3"><component><structuredBody><component><section><title>WARNINGS</title><text><paragraph>Use <content>with caution</content>.</paragraph></text></section></component></structuredBody></component></document>'''
    parsed = MedicalSourceClient._parse_dailymed_spl(xml)
    assert parsed["sections"][0]["original_text"] == "Use with caution ."
