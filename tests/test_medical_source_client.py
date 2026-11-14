from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

from services.medical_source_client import (
    DAILYMED_SPL_URL,
    MAX_RESPONSE_BYTES,
    MedicalSourceClient,
)


def response(payload: dict) -> Mock:
    item = Mock()
    item.content = json.dumps(payload).encode("utf-8")
    item.iter_content.return_value = [item.content]
    item.headers = {}
    item.status_code = 200
    item.raise_for_status.return_value = None
    item.close.return_value = None
    return item


@pytest.fixture
def session():
    return Mock()


@pytest.fixture
def client(session, tmp_path):
    return MedicalSourceClient(staging_root=tmp_path / "staging", session=session)


def assert_staged(result, expected_provider, expected_count):
    assert result.provider == expected_provider
    assert result.result_count == expected_count
    assert result.ingestion.review_status == "pending_clinical_review"
    assert result.ingestion.promotion_status == "staged_only"
    artifact = json.loads(Path(result.ingestion.artifact_path).read_text(encoding="utf-8"))
    assert artifact["metadata"]["canonical_url"].startswith("https://")
    assert artifact["payload"]


def test_fetches_and_stages_rxnorm_concept(client, session):
    session.get.return_value = response({"idGroup": {"rxnormId": ["6809"]}})
    result = client.fetch_and_stage_rxnorm_concept("metformin")
    assert_staged(result, "RxNav", 1)
    args, kwargs = session.get.call_args
    assert args[0] == "https://rxnav.nlm.nih.gov/REST/rxcui.json"
    assert kwargs["params"] == {"name": "metformin"}
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert kwargs["timeout"] > 0


def test_fetches_and_stages_openfda_label(client, session):
    session.get.return_value = response({"results": [{"id": "label-1"}, {"id": "label-2"}]})
    result = client.fetch_and_stage_openfda_label("aspirin", limit=2)
    assert_staged(result, "openFDA", 2)
    assert session.get.call_args.kwargs["params"]["limit"] == 2


def test_fetches_and_stages_dailymed_spl(client, session):
    import uuid
    setid = "123e4567-e89b-12d3-a456-426614174000"
    search = response({
        "columns": ["SETID", "TITLE", "SPL_VERSION", "PUBLISHED_DATE"],
        "data": [[setid, "Example label", "2", "2025-01-15"]],
    })
    xml = b"""<document xmlns="urn:hl7-org:v3"><title>Example label</title><component><structuredBody><component><section><code code="34067-9" displayName="INDICATIONS AND USAGE"/><title>INDICATIONS AND USAGE</title><text>Verbatim label text.</text></section></component></structuredBody></component></document>"""
    label = Mock()
    label.content = xml
    label.iter_content.return_value = [xml]
    label.headers = {"Content-Length": str(len(xml))}
    label.status_code = 200
    label.raise_for_status.return_value = None
    label.close.return_value = None
    session.get.side_effect = [search, label]

    result = client.fetch_and_stage_dailymed_labels("metformin", page_size=5)
    assert_staged(result, "DailyMed", 1)
    assert session.get.call_args_list[0].args[0] == DAILYMED_SPL_URL
    assert session.get.call_args_list[0].kwargs["params"] == {
        "drug_name": "metformin", "name_type": "both", "pagesize": 5, "page": 1
    }
    artifact = json.loads(Path(result.ingestion.artifact_path).read_text(encoding="utf-8"))
    assert artifact["payload"]["set_id"] == str(uuid.UUID(setid))
    assert artifact["payload"]["sections"][0]["original_text"] == "Verbatim label text."
    assert artifact["payload"]["review_status"] == "pending_clinical_review"


@pytest.mark.parametrize("method,args", [
    ("fetch_and_stage_rxnorm_concept", ("",)),
    ("fetch_and_stage_openfda_label", ("aspirin", 0)),
    ("fetch_and_stage_openfda_label", ("aspirin", 101)),
    ("fetch_and_stage_dailymed_labels", ("metformin", 101)),
])
def test_rejects_invalid_query_and_limits(client, method, args):
    with pytest.raises(ValueError):
        getattr(client, method)(*args)


def test_network_failure_is_typed(client, session):
    session.get.side_effect = requests.Timeout("timed out")
    from models.exceptions import ExternalAPIError
    with pytest.raises(ExternalAPIError):
        client.fetch_and_stage_rxnorm_concept("metformin")


def test_rejects_redirects(client, session):
    redirect = response({})
    redirect.status_code = 302
    session.get.return_value = redirect
    from models.exceptions import ExternalAPIError
    with pytest.raises(ExternalAPIError):
        client.fetch_and_stage_rxnorm_concept("metformin")
    assert session.get.call_args.kwargs["allow_redirects"] is False


def test_rejects_oversized_response_without_staging(client, session):
    oversized = Mock()
    oversized.content = b" " * (MAX_RESPONSE_BYTES + 1)
    oversized.iter_content.return_value = [oversized.content]
    oversized.headers = {}
    oversized.status_code = 200
    oversized.raise_for_status.return_value = None
    oversized.close.return_value = None
    session.get.return_value = oversized
    with pytest.raises(ValueError, match="exceeds"):
        client.fetch_and_stage_rxnorm_concept("metformin")
    assert not (client.staging_root / "index.json").exists()


def test_rejects_non_object_json_response(client, session):
    invalid = Mock()
    invalid.content = b'["not", "an", "object"]'
    invalid.iter_content.return_value = [invalid.content]
    invalid.headers = {}
    invalid.status_code = 200
    invalid.raise_for_status.return_value = None
    invalid.close.return_value = None
    session.get.return_value = invalid
    with pytest.raises(ValueError, match="JSON object"):
        client.fetch_and_stage_rxnorm_concept("metformin")


def test_no_live_fetch_promotes_runtime_knowledge(client, session, tmp_path):
    session.get.return_value = response({"results": [{"id": "label"}]})
    knowledge = Path(__file__).resolve().parent.parent / "knowledge"
    protected = ["interaction_rules.json", "food_rules.json", "evidence_sources.json"]
    before = {name: (knowledge / name).read_bytes() for name in protected}
    client.fetch_and_stage_openfda_label("metformin")
    after = {name: (knowledge / name).read_bytes() for name in protected}
    assert after == before
