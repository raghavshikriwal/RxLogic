"""
Live smoke test for services.llm_parser against a REAL, running Ollama
instance -- no mocking, unlike tests/test_llm_parser.py.

Run from the RxLogic project root (same folder as app.py):
    python live_llm_smoke_test.py

Prerequisites:
    - Ollama installed and serving (see steps in chat)
    - Model pulled: `ollama pull phi3:mini`
    - Same Python env as the rest of the project

This calls services.llm_parser.parse_medications() directly -- it
skips Flask, routing, and the built frontend entirely, so a failure
here means the LLM layer itself is the problem, not something else
in the stack.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models.exceptions import ExternalAPIError, SchemaValidationError
from services.llm_parser import parse_medications

TEST_CASES = [
    "I take metformin twice a day and just got prescribed aspirin",
    "lisinopril every morning, 10mg, and atorvastatin at night",
    "just started warfarin, also take ibuprofen when I have a headache",
]


def main() -> None:
    print("Testing services.llm_parser.parse_medications() against real Ollama\n")
    for i, text in enumerate(TEST_CASES, 1):
        print(f"--- Case {i}: {text!r} ---")
        try:
            medications = parse_medications(text)
            for m in medications:
                print(
                    f"  -> {m.name} | {m.frequency_per_day}x/day | "
                    f"timing={m.timing_preference.value} | "
                    f"dosage_mg={m.dosage_mg} | with_food={m.with_food}"
                )
        except ExternalAPIError as exc:
            print(f"  ExternalAPIError: {exc}")
            print("  -> Ollama unreachable/erroring. This is the graceful-degradation")
            print("     path -- expected if Ollama isn't installed or isn't running.")
        except SchemaValidationError as exc:
            print(f"  SchemaValidationError: {exc}")
            print("  -> Ollama responded, but the output didn't parse as the expected")
            print("     JSON schema. Worth looking at the raw_output in the error.")
        print()


if __name__ == "__main__":
    main()