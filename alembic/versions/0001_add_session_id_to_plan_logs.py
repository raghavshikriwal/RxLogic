"""add session_id to plan_logs

First real migration in this project -- Alembic was previously listed
in requirements.txt with no migrations directory behind it. This one
closes the P1 privacy defect: PlanLog rows had no owner, so GET
/api/plans returned every plan ever logged by every visitor.

Nullable on add so this is safe to run against a table that already
has rows (e.g. the live Render/Neon database) without a backfill step
-- pre-existing rows simply have no session_id and are excluded from
every session-scoped query going forward, which is the correct
behavior for data logged before scoping existed.

Revision ID: 0001
Revises:
Create Date: 2026-09-08
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plan_logs",
        sa.Column("session_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_plan_logs_session_id"),
        "plan_logs",
        ["session_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_plan_logs_session_id"), table_name="plan_logs")
    op.drop_column("plan_logs", "session_id")