"""
Natural-language -> structured Medication parsing (Layer 1, Section 4.1).

Calls a small, locally-hosted LLM via Ollama to extract medication
name, dosage, frequency and timing preference from free text. Output
is validated against the strict schema before ever reaching the
symbolic reasoning core (Section 4.1: the LLM never talks to the
reasoning engine directly with unstructured text).

Section 4.3 litmus test: this module is entirely optional. If Ollama
is unreachable or this file is never called, the system still works
end-to-end via structured input straight into
services.reasoning_service.generate_daily_plan().
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

from models.exceptions import ExternalAPIError, SchemaValidationError
from models.schemas import Medication, TimingPreference

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")

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


class LLMParser:
    """Thin, replaceable interface layer. Everything downstream of this
    class operates only on typed Medication objects, never on raw text."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model

    def parse(self, user_text: str) -> list[Medication]:
        raw_json = self._call_ollama(user_text)
        return self._validate_and_convert(raw_json)

    # -- LLM call -----------------------------------------------------------

    def _call_ollama(self, user_text: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_text},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.0,  # deterministic extraction, not creative generation
                        "num_predict": MAX_OUTPUT_TOKENS,  # bounded generation -- see comment above
                    },
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ExternalAPIError(api_name="Ollama", status_code=getattr(exc.response, "status_code", None)) from exc

        return response.json()["message"]["content"]

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