"""
Diagnostic: times a single Ollama call for the specific input that's
timing out in live_llm_smoke_test.py, with a generous timeout so we
can see the REAL duration and raw output instead of guessing.

Run from the project root:
    python diagnose_case2_timeout.py

Reuses the actual OLLAMA_BASE_URL, OLLAMA_MODEL, and _SYSTEM_PROMPT
from services/llm_parser.py -- this is the exact same request the
real code sends, just with timeout=180 instead of 30.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from services.llm_parser import OLLAMA_BASE_URL, OLLAMA_MODEL, _SYSTEM_PROMPT

FAILING_TEXT = "lisinopril every morning, 10mg, and atorvastatin at night"


def main() -> None:
    print(f"Model: {OLLAMA_MODEL} @ {OLLAMA_BASE_URL}")
    print(f"Input: {FAILING_TEXT!r}\n")
    print("Sending request (timeout=180s, just to observe -- not a fix)...\n")

    start = time.time()
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": FAILING_TEXT},
                ],
                "stream": False,
                "options": {"temperature": 0.0},
            },
            timeout=180,
        )
        elapsed = time.time() - start
        response.raise_for_status()
        content = response.json()["message"]["content"]

        print(f"SUCCEEDED after {elapsed:.1f}s\n")
        print("--- Raw model output ---")
        print(content)
        print("------------------------\n")

        if elapsed > 25:
            print(f"NOTE: {elapsed:.1f}s is close to or over your current 30s")
            print("REQUEST_TIMEOUT_SECONDS -- this explains the intermittent failure.")
        if not content.strip().startswith("["):
            print("NOTE: raw output does NOT start with '[' -- the model may be")
            print("adding preamble/reasoning before the JSON array, which both")
            print("wastes time and risks tripping SchemaValidationError too.")

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        print(f"STILL TIMED OUT after {elapsed:.1f}s (with a 180s budget).")
        print("This isn't a borderline-timeout issue -- something is actually")
        print("stuck (model looping, or serving a much larger/slower model).")
    except requests.RequestException as exc:
        print(f"Request failed differently: {exc}")


if __name__ == "__main__":
    main()