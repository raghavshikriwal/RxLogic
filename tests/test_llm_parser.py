"""
Tests for services/llm_parser.py

All Ollama calls are mocked -- these tests validate the parsing and
schema-validation logic, not the LLM's actual extraction quality (that
needs manual/qualitative evaluation separately, e.g. as part of the
three-way benchmark). No live Ollama instance is required to run these.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import requests

from models.exceptions import ExternalAPIError, SchemaValidationError
from models.schemas import TimingPreference
from services.llm_parser import LLMParser


def _mock_ollama_response(content: str) -> Mock:
    mock_response = Mock()
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"message": {"content": content}}
    return mock_response


@patch("services.llm_parser.requests.post")
def test_parses_well_formed_json_array(mock_post):
    mock_post.return_value = _mock_ollama_response(
        '[{"name": "metformin", "dosage_mg": null, "frequency_per_day": 2, '
        '"timing_preference": "no_preference", "with_food": true}]'
    )

    result = LLMParser().parse("I take metformin twice a day with food")

    assert len(result) == 1
    assert result[0].name == "metformin"
    assert result[0].frequency_per_day == 2
    assert result[0].with_food is True


@patch("services.llm_parser.requests.post")
def test_strips_markdown_code_fences(mock_post):
    mock_post.return_value = _mock_ollama_response(
        '```json\n[{"name": "aspirin", "frequency_per_day": 1}]\n```'
    )

    result = LLMParser().parse("just started aspirin")

    assert len(result) == 1
    assert result[0].name == "aspirin"


@patch("services.llm_parser.requests.post")
def test_defaults_applied_when_fields_omitted(mock_post):
    mock_post.return_value = _mock_ollama_response('[{"name": "lisinopril"}]')

    result = LLMParser().parse("taking lisinopril")

    assert result[0].frequency_per_day == 1
    assert result[0].timing_preference == TimingPreference.NO_PREFERENCE
    assert result[0].dosage_mg is None
    assert result[0].with_food is None


@patch("services.llm_parser.requests.post")
def test_multiple_medications_parsed(mock_post):
    mock_post.return_value = _mock_ollama_response(
        '[{"name": "metformin", "frequency_per_day": 2}, '
        '{"name": "aspirin", "frequency_per_day": 1}]'
    )

    result = LLMParser().parse("metformin twice a day and aspirin once")

    assert len(result) == 2
    assert {m.name for m in result} == {"metformin", "aspirin"}


@patch("services.llm_parser.requests.post")
def test_invalid_json_raises_schema_validation_error(mock_post):
    mock_post.return_value = _mock_ollama_response("not json at all")

    with pytest.raises(SchemaValidationError):
        LLMParser().parse("some input")


@patch("services.llm_parser.requests.post")
def test_non_array_json_raises_schema_validation_error(mock_post):
    mock_post.return_value = _mock_ollama_response('{"name": "metformin"}')

    with pytest.raises(SchemaValidationError):
        LLMParser().parse("some input")


@patch("services.llm_parser.requests.post")
def test_missing_name_field_raises_schema_validation_error(mock_post):
    mock_post.return_value = _mock_ollama_response('[{"frequency_per_day": 1}]')

    with pytest.raises(SchemaValidationError):
        LLMParser().parse("some input")


@patch("services.llm_parser.requests.post")
def test_invalid_timing_preference_raises_schema_validation_error(mock_post):
    mock_post.return_value = _mock_ollama_response(
        '[{"name": "metformin", "timing_preference": "whenever"}]'
    )

    with pytest.raises(SchemaValidationError):
        LLMParser().parse("some input")


@patch("services.llm_parser.requests.post")
def test_ollama_connection_failure_raises_external_api_error(mock_post):
    mock_post.side_effect = requests.ConnectionError("Ollama not running")

    with pytest.raises(ExternalAPIError):
        LLMParser().parse("some input")


@patch("services.llm_parser.requests.post")
def test_ollama_http_error_raises_external_api_error(mock_post):
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=500))
    mock_post.return_value = mock_response

    with pytest.raises(ExternalAPIError):
        LLMParser().parse("some input")