"""
Tests for the pluggable LLM providers in services/llm_parser.py.

Every HTTP call is mocked: these tests validate request construction,
configuration handling, error mapping and secret hygiene, not model quality.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import requests

from app import create_app
from models.exceptions import ExternalAPIError, SchemaValidationError
from models.schemas import Medication, TimingPreference
from services.llm_parser import (
    ANTHROPIC_API_URL,
    ANTHROPIC_API_VERSION,
    ANTHROPIC_MAX_OUTPUT_TOKENS,
    ANTHROPIC_TIMEOUT_SECONDS,
    DEFAULT_ANTHROPIC_MODEL,
    LLM_API_NAMES,
    AnthropicBackend,
    LLMParser,
    OllamaBackend,
    build_backend,
    parse_medications,
)

API_KEY = "sk-ant-test-secret-key"
VALID_ARRAY = (
    '[{"name": "sertraline", "dosage_mg": 50, "frequency_per_day": 1, '
    '"timing_preference": "morning", "with_food": null}]'
)


def _anthropic_response(text: str = VALID_ARRAY, *, blocks: object = None) -> Mock:
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"content": blocks if blocks is not None else [{"type": "text", "text": text}]}
    return response


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


# -- provider selection ---------------------------------------------------------


def test_default_provider_is_ollama():
    assert isinstance(build_backend({}), OllamaBackend)


@pytest.mark.parametrize("value", ["", "   ", "ollama", "OLLAMA", " Ollama "])
def test_ollama_provider_is_case_and_whitespace_insensitive(value):
    assert isinstance(build_backend({"LLM_PROVIDER": value}), OllamaBackend)


def test_ollama_settings_are_read_from_the_environment():
    backend = build_backend({"OLLAMA_BASE_URL": "http://llm.internal:11434", "OLLAMA_MODEL": "llama3"})

    assert backend.base_url == "http://llm.internal:11434"
    assert backend.model == "llama3"


def test_anthropic_provider_builds_backend_with_default_model():
    backend = build_backend({"LLM_PROVIDER": "Anthropic", "ANTHROPIC_API_KEY": f"  {API_KEY} "})

    assert isinstance(backend, AnthropicBackend)
    assert backend.model == DEFAULT_ANTHROPIC_MODEL


def test_anthropic_model_can_be_overridden_and_blank_falls_back_to_default():
    base = {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": API_KEY}

    assert build_backend({**base, "ANTHROPIC_MODEL": "custom-model"}).model == "custom-model"
    assert build_backend({**base, "ANTHROPIC_MODEL": "  "}).model == DEFAULT_ANTHROPIC_MODEL


@pytest.mark.parametrize("key", [None, "", "   "])
def test_anthropic_provider_without_api_key_is_a_configuration_error(key):
    environ = {"LLM_PROVIDER": "anthropic"}
    if key is not None:
        environ["ANTHROPIC_API_KEY"] = key

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_backend(environ)


def test_unsupported_provider_is_a_configuration_error():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        build_backend({"LLM_PROVIDER": "skynet"})


def test_anthropic_backend_rejects_a_blank_key():
    with pytest.raises(ValueError):
        AnthropicBackend(api_key="  ")


def test_parser_resolves_its_backend_from_the_process_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", API_KEY)

    with patch("services.llm_parser.requests.post", return_value=_anthropic_response()) as mock_post:
        result = parse_medications("sertraline 50 mg every morning")

    assert mock_post.call_args.args[0] == ANTHROPIC_API_URL
    assert [m.name for m in result] == ["sertraline"]


def test_parser_defaults_to_the_local_ollama_endpoint():
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"message": {"content": VALID_ARRAY}}

    with patch("services.llm_parser.requests.post", return_value=response) as mock_post:
        LLMParser().parse("sertraline 50 mg every morning")

    assert mock_post.call_args.args[0] == "http://localhost:11434/api/chat"
    assert mock_post.call_args.kwargs["json"]["stream"] is False


# -- Anthropic request/response handling ------------------------------------------


@patch("services.llm_parser.requests.post")
def test_anthropic_request_is_well_formed(mock_post):
    mock_post.return_value = _anthropic_response()

    AnthropicBackend(API_KEY, model="test-model").complete("SYSTEM PROMPT", "user text")

    assert mock_post.call_args.args == (ANTHROPIC_API_URL,)
    kwargs = mock_post.call_args.kwargs
    assert kwargs["headers"] == {
        "x-api-key": API_KEY,
        "anthropic-version": ANTHROPIC_API_VERSION,
        "content-type": "application/json",
    }
    assert kwargs["json"] == {
        "model": "test-model",
        "max_tokens": ANTHROPIC_MAX_OUTPUT_TOKENS,
        "temperature": 0.0,
        "system": "SYSTEM PROMPT",
        "messages": [{"role": "user", "content": "user text"}],
    }
    assert kwargs["timeout"] == ANTHROPIC_TIMEOUT_SECONDS


@patch("services.llm_parser.requests.post")
def test_anthropic_reply_is_parsed_into_typed_medications(mock_post):
    mock_post.return_value = _anthropic_response()

    result = LLMParser(AnthropicBackend(API_KEY)).parse("sertraline 50 mg every morning")

    assert len(result) == 1 and isinstance(result[0], Medication)
    assert result[0].name == "sertraline"
    assert result[0].dosage_mg == 50
    assert result[0].timing_preference == TimingPreference.MORNING


@patch("services.llm_parser.requests.post")
def test_anthropic_text_blocks_are_joined_and_other_blocks_ignored(mock_post):
    mock_post.return_value = _anthropic_response(
        blocks=[
            {"type": "thinking", "thinking": "ignored"},
            {"type": "text", "text": '[{"name": "aspirin", '},
            {"type": "text", "text": '"frequency_per_day": 2}]'},
        ]
    )

    result = LLMParser(AnthropicBackend(API_KEY)).parse("aspirin twice a day")

    assert [(m.name, m.frequency_per_day) for m in result] == [("aspirin", 2)]


@patch("services.llm_parser.requests.post")
def test_anthropic_output_still_passes_through_schema_validation(mock_post):
    mock_post.return_value = _anthropic_response("this is not json")

    with pytest.raises(SchemaValidationError):
        LLMParser(AnthropicBackend(API_KEY)).parse("anything")


@patch("services.llm_parser.requests.post")
def test_anthropic_decision_fields_injected_by_the_model_are_dropped(mock_post):
    mock_post.return_value = _anthropic_response(
        '[{"name": "warfarin", "frequency_per_day": 1, "severity": "none", "safe_to_combine": true}]'
    )

    result = LLMParser(AnthropicBackend(API_KEY)).parse("warfarin")

    assert not hasattr(result[0], "severity") and not hasattr(result[0], "safe_to_combine")


@pytest.mark.parametrize(
    "blocks",
    [[], [{"type": "text", "text": "   "}], [{"type": "tool_use", "id": "x"}], "not-a-list", None],
)
@patch("services.llm_parser.requests.post")
def test_anthropic_reply_without_text_raises_external_api_error(mock_post, blocks):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {"content": blocks}
    mock_post.return_value = response

    with pytest.raises(ExternalAPIError) as excinfo:
        AnthropicBackend(API_KEY).complete("system", "user")

    assert excinfo.value.api_name == "Anthropic"


@patch("services.llm_parser.requests.post")
def test_anthropic_non_object_payload_raises_external_api_error(mock_post):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = ["unexpected"]
    mock_post.return_value = response

    with pytest.raises(ExternalAPIError):
        AnthropicBackend(API_KEY).complete("system", "user")


@pytest.mark.parametrize("status", [401, 429, 500, 529])
@patch("services.llm_parser.requests.post")
def test_anthropic_http_errors_carry_the_status_code(mock_post, status):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError(response=Mock(status_code=status))
    mock_post.return_value = response

    with pytest.raises(ExternalAPIError) as excinfo:
        AnthropicBackend(API_KEY).complete("system", "user")

    assert excinfo.value.api_name == "Anthropic"
    assert excinfo.value.status_code == status


@pytest.mark.parametrize("failure", [requests.ConnectionError("down"), requests.Timeout("slow")])
@patch("services.llm_parser.requests.post")
def test_anthropic_network_failures_raise_external_api_error(mock_post, failure):
    mock_post.side_effect = failure

    with pytest.raises(ExternalAPIError) as excinfo:
        AnthropicBackend(API_KEY).complete("system", "user")

    assert excinfo.value.status_code is None


@patch("services.llm_parser.requests.post")
def test_anthropic_non_json_body_raises_external_api_error(mock_post):
    response = Mock()
    response.raise_for_status = Mock()
    response.json.side_effect = ValueError("not json")
    mock_post.return_value = response

    with pytest.raises(ExternalAPIError):
        AnthropicBackend(API_KEY).complete("system", "user")


@patch("services.llm_parser.requests.post")
def test_failures_never_leak_the_api_key_or_user_text(mock_post, caplog):
    secret_text = "my private medication history"
    mock_post.side_effect = requests.ConnectionError(f"boom {API_KEY} {secret_text}")

    with caplog.at_level("DEBUG"):
        with pytest.raises(ExternalAPIError) as excinfo:
            AnthropicBackend(API_KEY).complete("system", secret_text)

    assert API_KEY not in str(excinfo.value) and secret_text not in str(excinfo.value)
    assert API_KEY not in caplog.text and secret_text not in caplog.text


# -- API error mapping ------------------------------------------------------------


def test_every_llm_provider_name_is_registered_for_error_mapping():
    assert LLM_API_NAMES == {"Ollama", "Anthropic"}


@patch("routes.api.parse_medications")
def test_anthropic_failure_maps_to_llm_api_error_502(mock_parse, client):
    mock_parse.side_effect = ExternalAPIError(api_name="Anthropic", status_code=429)

    response = client.post("/api/plan/nl", json={"text": "sertraline once a day"})

    assert response.status_code == 502
    assert response.get_json()["error"] == "llm_api_error"


@patch("routes.api.parse_medications")
def test_llm_configuration_error_maps_to_503_without_touching_structured_planning(mock_parse, client):
    mock_parse.side_effect = ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")

    response = client.post("/api/plan/nl", json={"text": "sertraline once a day"})

    assert response.status_code == 503
    assert response.get_json()["error"] == "configuration_error"
