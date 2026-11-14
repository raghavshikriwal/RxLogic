"""Shared Flask extension instances.

The storage URI is configurable so production deployments can use a shared
Redis backend. `memory://` remains a development/test convenience only; it is
process-local and does not coordinate limits across Gunicorn workers.
"""
from __future__ import annotations

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60 per minute"],
)
