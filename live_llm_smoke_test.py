"""
Live smoke test for services.llm_parser against the REAL configured provider
-- no mocking, unlike tests/test_llm_parser.py and tests/test_llm_providers.py.

Run from the project root (same folder as app.py):

    # Local Ollama (default): `ollama pull phi3:mini` and `ollama serve` first
    python live_llm_smoke_test.py

    # Hosted Anthropic API (PowerShell):
    $env:LLM_PROVIDER = "anthropic"
    $env:ANTHROPIC_API_KEY = "<your key>"
    python live_llm_smoke_test.py

This calls services.llm_parser.parse_medications() directly, skipping Flask,
routing and the frontend, so a failure here means the LLM layer itself is the
problem. Use synthetic text only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv

load_dotenv()

from models.exceptions import ExternalAPIError, SchemaValidationError
from services.llm_parser import build_backend, parse_medications

TEST_CASES = [
    "I take metformin twice a day and just got prescribed aspirin",
    "lisinopril every morning, 10mg, and atorvastatin at night",
    "just started warfarin, also take ibuprofen when I have a headache",
]


def main() -> int:
    try:
        backend = build_backend()
    except ValueError as exc:
        print(f"Configuration error: {exc}")
        return 2

    print(f"Provider: {backend.api_name} (model: {getattr(backend, 'model', 'n/a')})\n")
    failures = 0
    for index, text in enumerate(TEST_CASES, 1):
        print(f"--- Case {index}: {text!r} ---")
        try:
            for medication in parse_medications(text):
                print(
                    f"  -> {medication.name} | {medication.frequency_per_day}x/day | "
                    f"timing={medication.timing_preference.value} | "
                    f"dosage_mg={medication.dosage_mg} | with_food={medication.with_food}"
                )
        except ExternalAPIError as exc:
            failures += 1
            print(f"  ExternalAPIError: {exc}")
            print("  -> Provider unreachable or rejected the request (check key, model, network).")
        except SchemaValidationError as exc:
            failures += 1
            print(f"  SchemaValidationError: {exc}")
            print("  -> Provider replied, but the output did not match the expected JSON schema.")
        print()

    print("PASS" if not failures else f"{failures} case(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
