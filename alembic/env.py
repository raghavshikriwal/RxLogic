"""
Alembic migration environment for RxLogic.

Deliberately thin: target_metadata and the database URL are both
pulled directly from models/database.py rather than duplicated here,
so a migration always targets the exact same engine configuration
(including the postgres:// -> postgresql:// normalization) that the
running app itself uses. There is no separate "migrations database
config" to drift out of sync with app.py.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Repo root must be importable so `models.database` resolves the same
# way it does when the Flask app itself imports it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Must run before importing models.database: that module reads
# DATABASE_URL at import time (module-level `os.getenv` call). app.py
# calls load_dotenv() before its own import of models.database for
# the identical reason (see app.py's comment) -- alembic is a second,
# independent entry point into that same module, so it needs the same
# guard, or it silently falls back to an uninitialized in-memory
# SQLite database instead of the real target (Postgres in production,
# a file-based dev DB locally).
load_dotenv()

from models.database import Base, DATABASE_URL  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Enables `alembic revision --autogenerate` to diff against the ORM
# models instead of every migration being hand-written from scratch.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade
    --sql`). Not used in the normal dev/deploy flow, but kept so the
    standard Alembic offline-mode escape hatch still works."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the real database and run migrations -- the path used
    by `alembic upgrade head` in dev and in the Render deploy step."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()