"""
Shared Flask extension instances.

Kept separate from app.py so that routes/api.py can import `limiter`
without creating a circular import back to the app factory.
"""

from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Section 6.3: rate-limit-aware design. Default limits protect the
# external-facing API from abuse; RxNav/openFDA calls are already
# cached at the drug_data_client layer, so this mainly guards the
# reasoning endpoints themselves.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute"],
    storage_uri="memory://",
)