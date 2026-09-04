"""
Tests for services/drug_data_client.py

All RxNav/openFDA calls are mocked -- no live network access is needed
to run these. Every test uses a temp cache directory (tmp_path fixture)
instead of the real knowledge/cache/ folder that scripts/build_knowledge_base.py
populates, so these tests never read stale cache entries or leave files
behind for other tests/runs to trip over.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import requests

from models.exceptions import ExternalAPIError
from services.drug_data_client import DrugDataClient


@pytest.fixture()
def client(tmp_path):
    return DrugDataClient(cache_dir=tmp_path)


def _mock_response(payload: dict) -> Mock:
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = payload
    return mock_response


# -- get_rxcui ----------------------------------------------------------------


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_rxcui_returns_first_id(mock_get, mock_sleep, client):
    mock_get.return_value = _mock_response({"idGroup": {"rxnormId": ["6809", "999999"]}})

    rxcui = client.get_rxcui("metformin")

    assert rxcui == "6809"
    mock_sleep.assert_called_once()  # the polite rate-limit delay was applied


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_rxcui_second_call_is_served_from_cache(mock_get, mock_sleep, client):
    mock_get.return_value = _mock_response({"idGroup": {"rxnormId": ["6809"]}})

    first = client.get_rxcui("metformin")
    second = client.get_rxcui("metformin")

    assert first == second == "6809"
    mock_get.assert_called_once()  # no second network call once cached


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_rxcui_returns_none_when_medication_unmatched(mock_get, mock_sleep, client):
    mock_get.return_value = _mock_response({"idGroup": {}})

    assert client.get_rxcui("not-a-real-drug") is None


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_rxcui_connection_failure_raises_external_api_error(mock_get, mock_sleep, client):
    mock_get.side_effect = requests.ConnectionError("network unreachable")

    with pytest.raises(ExternalAPIError) as exc_info:
        client.get_rxcui("metformin")
    assert exc_info.value.api_name == "RxNav"


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_rxcui_http_error_raises_external_api_error_with_status(mock_get, mock_sleep, client):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=503))
    mock_get.return_value = mock_response

    with pytest.raises(ExternalAPIError) as exc_info:
        client.get_rxcui("metformin")
    assert exc_info.value.status_code == 503


# -- get_drug_label -------------------------------------------------------------


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_drug_label_returns_full_payload(mock_get, mock_sleep, client):
    payload = {"results": [{"warnings": ["may cause drowsiness"]}]}
    mock_get.return_value = _mock_response(payload)

    label = client.get_drug_label("aspirin")

    assert label == payload


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_drug_label_second_call_is_served_from_cache(mock_get, mock_sleep, client):
    mock_get.return_value = _mock_response({"results": [{"warnings": []}]})

    client.get_drug_label("aspirin")
    client.get_drug_label("aspirin")

    mock_get.assert_called_once()


@patch("services.drug_data_client.time.sleep")
@patch("services.drug_data_client.requests.get")
def test_get_drug_label_connection_failure_raises_external_api_error(mock_get, mock_sleep, client):
    mock_get.side_effect = requests.ConnectionError("network unreachable")

    with pytest.raises(ExternalAPIError) as exc_info:
        client.get_drug_label("aspirin")
    assert exc_info.value.api_name == "openFDA"


# -- cache internals ------------------------------------------------------------


def test_cache_path_sanitizes_slashes_spaces_and_case(client, tmp_path):
    path = client._cache_path("Some Drug/Name")

    assert path == tmp_path / "some_drug_name.json"


def test_read_cache_returns_none_when_file_does_not_exist(client):
    assert client._read_cache("nonexistent_key") is None


def test_write_cache_then_read_cache_round_trips(client):
    client._write_cache("rxcui_metformin", {"rxcui": "6809"})

    assert client._read_cache("rxcui_metformin") == {"rxcui": "6809"}