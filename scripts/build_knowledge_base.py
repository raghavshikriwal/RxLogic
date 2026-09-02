"""
One-off script to resolve seed medications to RxCUIs (via RxNav, still
live) and merge them with the manually curated interaction rule set.

Note: RxNav's live Drug-Drug Interaction API was discontinued by NLM
in Jan 2024 — see README Scope & Limitations. Interaction data here
is curated, not pulled live.

Run from the project root:
    python -m scripts.build_knowledge_base
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.drug_data_client import DrugDataClient
from models.exceptions import ExternalAPIError

SEED_MEDICATIONS = [
    "metformin", "aspirin", "lisinopril", "atorvastatin", "warfarin",
    "ibuprofen", "omeprazole", "metoprolol", "amoxicillin", "levothyroxine",
]

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "interaction_rules.json"


def resolve_medications(client: DrugDataClient, names: list[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name in names:
        try:
            rxcui = client.get_rxcui(name)
            if rxcui:
                resolved[name] = rxcui
                print(f"  resolved: {name} -> RxCUI {rxcui}")
            else:
                print(f"  WARNING: could not resolve '{name}' — skipping")
        except ExternalAPIError as exc:
            print(f"  ERROR resolving '{name}': {exc}")
    return resolved


def main() -> None:
    client = DrugDataClient()

    print("Resolving seed medications to RxCUIs (RxNorm — still live)...")
    resolved = resolve_medications(client, SEED_MEDICATIONS)

    existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    existing["medications"] = resolved

    OUTPUT_PATH.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"\nDone. {len(resolved)} medications resolved, "
          f"{len(existing['interaction_rules'])} curated interaction rules in place.")
    print(f"Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()