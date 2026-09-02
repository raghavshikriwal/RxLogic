"""
Client for RxNav (NLM) and openFDA APIs, with local JSON caching.

Both APIs are free and require no API key. Caching avoids redundant
network calls and keeps the reasoning core usable offline once the
cache is warm (Section 6.3: rate-limit-aware wrapper with local caching).

Note: RxNav's live Drug-Drug Interaction API was discontinued by NLM
in Jan 2024. This client only resolves RxCUIs (still live) and fetches
openFDA label data. Interaction rules are curated separately —
see knowledge/interaction_rules.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import requests

from models.exceptions import ExternalAPIError

RXNAV_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
OPENFDA_BASE_URL = "https://api.fda.gov/drug"

CACHE_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT_SECONDS = 10
RATE_LIMIT_DELAY_SECONDS = 0.3  # polite delay between calls


class DrugDataClient:
    """Thin wrapper around RxNav + openFDA with file-based caching."""

    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir

    def _cache_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace(" ", "_").lower()
        return self.cache_dir / f"{safe_key}.json"

    def _read_cache(self, key: str) -> Optional[dict[str, Any]]:
        path = self._cache_path(key)
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return None

    def _write_cache(self, key: str, data: dict[str, Any]) -> None:
        path = self._cache_path(key)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _get(self, url: str, params: dict[str, Any], api_name: str) -> dict[str, Any]:
        try:
            response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            time.sleep(RATE_LIMIT_DELAY_SECONDS)
            return response.json()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            raise ExternalAPIError(api_name, status_code=status) from exc

    def get_rxcui(self, medication_name: str) -> Optional[str]:
        """Resolve a medication name to an RxNav concept ID (RxCUI)."""
        cache_key = f"rxcui_{medication_name}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached.get("rxcui")

        data = self._get(
            f"{RXNAV_BASE_URL}/rxcui.json",
            params={"name": medication_name},
            api_name="RxNav",
        )
        rxcui_list = data.get("idGroup", {}).get("rxnormId", [])
        rxcui = rxcui_list[0] if rxcui_list else None
        self._write_cache(cache_key, {"rxcui": rxcui})
        return rxcui

    def get_drug_label(self, medication_name: str) -> dict[str, Any]:
        """Fetch openFDA label data (adverse reactions, warnings) for a medication."""
        cache_key = f"label_{medication_name}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        data = self._get(
            f"{OPENFDA_BASE_URL}/label.json",
            params={"search": f'openfda.generic_name:"{medication_name}"', "limit": 1},
            api_name="openFDA",
        )
        self._write_cache(cache_key, data)
        return data