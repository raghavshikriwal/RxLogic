"""Cross-check catalog RxCUIs against NLM RxNav.

The medication catalog is an identity registry: a wrong RxCUI silently
attaches a medication to the wrong ingredient. This module verifies, for
each canonical name, that RxNav returns the same ingredient name for the
recorded RxCUI. It checks identity only; it says nothing about clinical
knowledge. Network access is injected via a ``requests.Session``-like
object so the logic is testable offline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import requests

from services.drug_data_client import RATE_LIMIT_DELAY_SECONDS, REQUEST_TIMEOUT_SECONDS, RXNAV_BASE_URL

INGREDIENT_TERM_TYPE = "IN"

STATUS_MATCH = "match"
STATUS_NAME_MISMATCH = "name_mismatch"
STATUS_NOT_INGREDIENT = "not_ingredient"
STATUS_NOT_FOUND = "not_found"
STATUS_ERROR = "error"


class _Session(Protocol):
    def get(self, url: str, *, timeout: float) -> Any: ...


@dataclass(frozen=True)
class RxcuiCheck:
    """Outcome of verifying one catalog entry against RxNav."""
    canonical_name: str
    rxcui: str
    status: str
    rxnav_name: str | None = None
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == STATUS_MATCH


def _check_one(name: str, rxcui: str, session: _Session, timeout: float) -> RxcuiCheck:
    url = f"{RXNAV_BASE_URL}/rxcui/{rxcui}/properties.json"
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        return RxcuiCheck(name, rxcui, STATUS_ERROR, detail=f"{type(exc).__name__}: {exc}")

    properties = payload.get("properties") if isinstance(payload, dict) else None
    if not properties:
        return RxcuiCheck(name, rxcui, STATUS_NOT_FOUND, detail="RxNav returned no properties")
    rxnav_name = str(properties.get("name", ""))
    if properties.get("tty") != INGREDIENT_TERM_TYPE:
        return RxcuiCheck(name, rxcui, STATUS_NOT_INGREDIENT, rxnav_name, f"term type {properties.get('tty')!r}")
    if rxnav_name.casefold() != name.casefold():
        return RxcuiCheck(name, rxcui, STATUS_NAME_MISMATCH, rxnav_name)
    return RxcuiCheck(name, rxcui, STATUS_MATCH, rxnav_name)


def verify_rxcuis(
    rxcuis: Mapping[str, str],
    session: _Session | None = None,
    *,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
    delay: float = RATE_LIMIT_DELAY_SECONDS,
) -> list[RxcuiCheck]:
    """Verify every ``canonical name -> RxCUI`` pair; never raises on network errors."""
    client = session or requests.Session()
    results: list[RxcuiCheck] = []
    for index, (name, rxcui) in enumerate(sorted(rxcuis.items())):
        if index and delay:
            time.sleep(delay)
        results.append(_check_one(name, str(rxcui), client, timeout))
    return results
