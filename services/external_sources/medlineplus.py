"""MedlinePlus Connect reference-link helper.

This connector intentionally returns a reference URL only. It does not copy,
cache, or redistribute MedlinePlus article content.
"""
from __future__ import annotations
from urllib.parse import urlencode

BASE_URL = "https://connect.medlineplus.gov/service"
RXNORM_VOCABULARY_OID = "2.16.840.1.113883.6.88"


def medication_reference_url(rxcui: str) -> str:
    value = str(rxcui).strip()
    if not value.isdigit() or len(value) > 12:
        raise ValueError("rxcui must be a numeric RxNorm identifier")
    params = {
        "mainSearchCriteria.v.cs": RXNORM_VOCABULARY_OID,
        "mainSearchCriteria.v.c": value,
        "knowledgeResponseType": "application/json",
    }
    return f"{BASE_URL}?{urlencode(params)}"
