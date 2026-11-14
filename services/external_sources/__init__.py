"""Official medication-source connectors for Task 16.

Connectors retrieve public source snapshots only. All retrieved documents are
handed to the existing immutable evidence staging workflow; none can approve or
publish clinical knowledge.
"""
from services.external_sources.base import SourceCapability, SourceConnectorResult
from services.external_sources.registry import available_source_capabilities

__all__ = ["SourceCapability", "SourceConnectorResult", "available_source_capabilities"]
