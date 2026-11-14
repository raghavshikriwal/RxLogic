"""
Natural-language -> structured Medication parsing (Layer 1, Section 4.1).

Extracts medication name, dosage, frequency and timing preference from free
text using a pluggable LLM backend:

* ``ollama``    -- a locally hosted model (default; no data leaves the machine).
* ``anthropic`` -- Anthropic's hosted Messages API (paid).
* ``gemini``    -- Google Gemini API via its OpenAI-compatible endpoint (free tier).
* ``groq``      -- Groq's OpenAI-compatible API (free tier).

The provider is resolved at call time from the environment (``LLM_PROVIDER``),
so deployment configuration changes never require a code change. Whatever a
backend returns is treated as untrusted text: it is validated against the
strict schema before reaching the symbolic reasoning core (Section 4.1), and
this module depends only on ``models.*``.

Section 4.3 litmus test: this module is entirely optional. If the backend is
unreachable or this file is never called, the system still works end-to-end
via structured input straight into
services.reasoning_service.generate_daily_plan().
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Mapping, Protocol

import requests

from models.exceptions import ExternalAPIError, SchemaValidationError
from models.schemas import Medication, TimingPreference

logger = logging.getLogger(__name__)

# -- provider registry --------------------------------------------------------

PROVIDER_OLLAMA = "ollama"
PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_GEMINI = "gemini"
PROVIDER_GROQ = "groq"
SUPPORTED_PROVIDERS = (PROVIDER_OLLAMA, PROVIDER_ANTHROPIC, PROVIDER_GEMINI, PROVIDER_GROQ)
DEFAULT_PROVIDER = PROVIDER_OLLAMA

OLLAMA_API_NAME = "Ollama"
ANTHROPIC_API_NAME = "Anthropic"
GEMINI_API_NAME = "Gemini"
GROQ_API_NAME = "Groq"
# Every ExternalAPIError.api_name that means "the LLM layer failed". The API
# layer maps these to the `llm_api_error` code so clients can fall back to
# structured input.
LLM_API_NAMES = frozenset({OLLAMA_API_NAME, ANTHROPIC_API_NAME, GEMINI_API_NAME, GROQ_API_NAME})

# -- Ollama (local) -----------------------------------------------------------

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "phi3:mini"
# Import-time values are retained for scripts (e.g. diagnose_case2_timeout.py);
# the parser itself resolves configuration when a backend is built.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)

# 60s rather than a tighter bound: local CPU inference speed varies a lot
# across machines, and this is a hard ceiling for the whole request, not
# just generation -- it also covers model load time on a cold Ollama start.
REQUEST_TIMEOUT_SECONDS = 60

# Caps how many tokens the model may generate for a single extraction call.
#
# Diagnosed via a live test against a real Ollama instance: with
# temperature=0.0 (greedy decoding) and no generation cap, phi3:mini could
# fall into a repetition loop on certain inputs and never emit a stop
# token -- reproduced hanging past 180s on one specific, deterministic
# input, while REQUEST_TIMEOUT_SECONDS alone only limited how long the
# *caller* waited, not how long Ollama kept generating in the background.
# A medication-extraction JSON array never legitimately needs more than a
# few dozen tokens per medication, so this is a generous ceiling that costs
# nothing on the happy path but guarantees every request resolves in
# bounded time instead of tying up a worker indefinitely.
MAX_OUTPUT_TOKENS = 300

# -- Anthropic (hosted) -------------------------------------------------------

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"
# Hosted inference is fast; a short ceiling frees web workers quickly.
ANTHROPIC_TIMEOUT_SECONDS = 30
# Sized for the API's 25-medication request cap (a few dozen tokens each).
ANTHROPIC_MAX_OUTPUT_TOKENS = 1024
EXTRACTION_TEMPERATURE = 0.0  # deterministic extraction, not creative generation

# -- OpenAI-compatible hosted APIs (Gemini, Groq: both have free tiers) --------
# Both expose POST {base}/chat/completions with a Bearer key. Model names change
# often, so they are only defaults: override with GEMINI_MODEL / GROQ_MODEL.

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
OPENAI_COMPAT_TIMEOUT_SECONDS = 30
OPENAI_COMPAT_MAX_OUTPUT_TOKENS = 1024

_SYSTEM_PROMPT = """You are a strict information-extraction module. Given a user's \
free-text description of medications they take, extract a JSON array of \
medication objects. Output ONLY the JSON array -- no prose, no markdown fences.

Each object must have exactly these fields:
- "name": string, the medication name as written (do not correct spelling)
- "dosage_mg": number or null, the dose in milligrams if stated
- "frequency_per_day": integer, how many times per day (default 1 if unstated)
- "timing_preference": one of "morning", "afternoon", "evening", "night", \
"no_preference" (default "no_preference" if unstated)
- "with_food": true, false, or null if unspecified

Example input: "I take metformin twice a day and just got prescribed aspirin"
Example output:
[
  {"name": "metformin", "dosage_mg": null, "frequency_per_day": 2, "timing_preference": "no_preference", "with_food": null},
  {"name": "aspirin", "dosage_mg": null, "frequency_per_day": 1, "timing_preference": "no_preference", "with_food": null}
]
"""


# -- backends -----------------------------------------------------------------


class LLMBackend(Protocol):
    """One text-completion provider. Implementations raise ExternalAPIError on
    any transport, HTTP or response-shape failure and never log user text or
    credentials."""

    api_name: str

    def complete(self, system_prompt: str, user_text: str) -> str:
        """Return the model's raw text reply."""


class OllamaBackend:
    """Locally hosted model served by Ollama."""

    api_name = OLLAMA_API_NAME

    def __init__(self, base_url: str = DEFAULT_OLLAMA_BASE_URL, model: str = DEFAULT_OLLAMA_MODEL) -> None:
        self.base_url = base_url
        self.model = model

    def complete(self, system_prompt: str, user_text: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": EXTRACTION_TEMPERATURE,
                        "num_predict": MAX_OUTPUT_TOKENS,  # bounded generation -- see above
                    },
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ExternalAPIError(api_name=self.api_name, status_code=getattr(exc.response, "status_code", None)) from exc

        return response.json()["message"]["content"]


class AnthropicBackend:
    """Anthropic's hosted Messages API, called over plain HTTPS (no SDK)."""

    api_name = ANTHROPIC_API_NAME

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        api_url: str = ANTHROPIC_API_URL,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("an Anthropic API key is required")
        self._api_key = api_key.strip()
        self.model = model
        self._api_url = api_url

    def complete(self, system_prompt: str, user_text: str) -> str:
        try:
            response = requests.post(
                self._api_url,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": ANTHROPIC_API_VERSION,
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": ANTHROPIC_MAX_OUTPUT_TOKENS,
                    "temperature": EXTRACTION_TEMPERATURE,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_text}],
                },
                timeout=ANTHROPIC_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # Log the failure class and status only: never the request (user
            # text, API key) or the response body.
            logger.warning("Anthropic request failed (%s, status=%s)", type(exc).__name__, status_code)
            raise ExternalAPIError(api_name=self.api_name, status_code=status_code) from exc

        return self._extract_text(payload)

    def _extract_text(self, payload: Any) -> str:
        """Concatenate the reply's text blocks; anything else is an upstream fault."""
        blocks = payload.get("content") if isinstance(payload, dict) else None
        text = ""
        if isinstance(blocks, list):
            text = "".join(
                block["text"]
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
            )
        if not text.strip():
            logger.warning("Anthropic response contained no text content")
            raise ExternalAPIError(api_name=self.api_name)
        return text


class OpenAICompatibleBackend:
    """Any hosted API that speaks the OpenAI chat-completions format (Gemini,
    Groq, ...), called over plain HTTPS (no SDK)."""

    def __init__(self, api_name: str, api_url: str, api_key: str, model: str) -> None:
        if not api_key or not api_key.strip():
            raise ValueError(f"a {api_name} API key is required")
        self.api_name = api_name
        self._api_url = api_url
        self._api_key = api_key.strip()
        self.model = model

    def complete(self, system_prompt: str, user_text: str) -> str:
        try:
            response = requests.post(
                self._api_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": EXTRACTION_TEMPERATURE,
                    "max_tokens": OPENAI_COMPAT_MAX_OUTPUT_TOKENS,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_text},
                    ],
                },
                timeout=OPENAI_COMPAT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # Failure class and status only: never the request or response body.
            logger.warning("%s request failed (%s, status=%s)", self.api_name, type(exc).__name__, status_code)
            raise ExternalAPIError(api_name=self.api_name, status_code=status_code) from exc

        return self._extract_text(payload)

    def _extract_text(self, payload: Any) -> str:
        text = None
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            pass
        if not isinstance(text, str) or not text.strip():
            logger.warning("%s response contained no text content", self.api_name)
            raise ExternalAPIError(api_name=self.api_name)
        return text


def _setting(env: Mapping[str, str], name: str, default: str = "") -> str:
    """Return a trimmed setting, treating unset and blank values as the default."""
    return (env.get(name) or "").strip() or default


def build_backend(environ: Mapping[str, str] | None = None) -> LLMBackend:
    """Build the configured backend from environment settings.

    Raises ValueError for an unsupported provider or a missing credential, so a
    misconfiguration surfaces as a configuration error rather than as a
    misleading "LLM unreachable" failure.
    """
    env = os.environ if environ is None else environ
    provider = _setting(env, "LLM_PROVIDER", DEFAULT_PROVIDER).lower()

    if provider == PROVIDER_OLLAMA:
        return OllamaBackend(
            base_url=_setting(env, "OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL),
            model=_setting(env, "OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL),
        )
    if provider == PROVIDER_ANTHROPIC:
        api_key = _setting(env, "ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicBackend(api_key=api_key, model=_setting(env, "ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL))
    if provider == PROVIDER_GEMINI:
        api_key = _setting(env, "GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return OpenAICompatibleBackend(
            GEMINI_API_NAME, GEMINI_API_URL, api_key, _setting(env, "GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        )
    if provider == PROVIDER_GROQ:
        api_key = _setting(env, "GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        return OpenAICompatibleBackend(
            GROQ_API_NAME, GROQ_API_URL, api_key, _setting(env, "GROQ_MODEL", DEFAULT_GROQ_MODEL)
        )
    raise ValueError(f"LLM_PROVIDER must be one of: {', '.join(SUPPORTED_PROVIDERS)}")


# -- parser -------------------------------------------------------------------


class LLMParser:
    """Thin, replaceable interface layer. Everything downstream of this
    class operates only on typed Medication objects, never on raw text."""

    def __init__(self, backend: LLMBackend | None = None) -> None:
        self._backend = backend if backend is not None else build_backend()

    def parse(self, user_text: str) -> list[Medication]:
        raw_json = self._backend.complete(_SYSTEM_PROMPT, user_text)
        return self._validate_and_convert(raw_json)

    # -- validation: raw LLM text -> typed Medication objects ----------------

    def _validate_and_convert(self, raw_content: str) -> list[Medication]:
        cleaned = raw_content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        # raw_decode (not json.loads) deliberately stops after the first
        # complete JSON value and ignores anything after it. Diagnosed via
        # a live test: even with MAX_OUTPUT_TOKENS capping generation,
        # phi3:mini sometimes emits a fully valid array and then keeps
        # generating more content instead of stopping. json.loads correctly
        # (but unhelpfully) rejects that whole response as "Extra data" --
        # the array itself was still valid, we just need to stop reading
        # at the end of it instead of demanding the entire string be
        # exactly one JSON document.
        try:
            parsed, _ = json.JSONDecoder().raw_decode(cleaned)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(raw_output=raw_content, validation_errors=f"not valid JSON: {exc}") from exc

        if not isinstance(parsed, list):
            raise SchemaValidationError(raw_output=raw_content, validation_errors="expected a JSON array")

        return [self._to_medication(entry, raw_content) for entry in parsed]

    def _to_medication(self, entry: dict[str, Any], raw_content: str) -> Medication:
        try:
            name = entry["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValueError("'name' must be a non-empty string")

            timing_raw = entry.get("timing_preference", TimingPreference.NO_PREFERENCE.value) or TimingPreference.NO_PREFERENCE.value
            timing_preference = TimingPreference(timing_raw)

            return Medication(
                name=name,
                dosage_mg=entry.get("dosage_mg"),
                frequency_per_day=int(entry.get("frequency_per_day") or 1),
                timing_preference=timing_preference,
                with_food=entry.get("with_food"),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise SchemaValidationError(raw_output=raw_content, validation_errors=str(exc)) from exc


def parse_medications(user_text: str) -> list[Medication]:
    """Module-level convenience wrapper, mirroring reasoning_service's pattern."""
    return LLMParser().parse(user_text)
