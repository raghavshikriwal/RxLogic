"""Source capability registry exposed to the API without live network calls."""
from __future__ import annotations
from services.external_sources.base import SourceCapability


def available_source_capabilities() -> list[dict[str, str]]:
    items = (
        SourceCapability("rxnorm", "RxNorm / RxNav", "US", "available", "Medication identity, RxCUI and terminology lookup; not a clinical monograph.", "https://lhncbc.nlm.nih.gov/RxNav/APIs/index.html"),
        SourceCapability("dailymed", "DailyMed", "US", "available", "Structured product-label search; product and jurisdiction applicability require review.", "https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm"),
        SourceCapability("openfda", "openFDA", "US", "available", "Public drug-label data; submissions are not independently clinically verified.", "https://open.fda.gov/apis/drug/label/"),
        SourceCapability("medlineplus", "MedlinePlus Connect", "US", "reference_only", "Provides an external reference link; RxLogic does not copy or redistribute article content.", "https://medlineplus.gov/medlineplus-connect/web-service/"),
        SourceCapability("india_regulatory", "India regulatory sources", "IN", "not_configured", "Connector interface reserved for approved CDSCO or official product-document sources; no unverified scraping.", "https://cdsco.gov.in/"),
    )
    return [item.__dict__.copy() for item in items]
