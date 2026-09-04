"""
Persistence service -- translates typed DailyPlan objects into
PlanLog rows and back. This is the only module that imports both
models.schemas (the reasoning core's types) and models.database (the
persistence layer), keeping the two schema boundaries (Section 6.1)
from leaking into each other: services.reasoning_service never
imports SQLAlchemy, and models.database never imports the reasoning
core's dataclasses.
"""

from __future__ import annotations

from dataclasses import asdict

from models.database import PlanLog, get_session
from models.schemas import DailyPlan, Medication


def log_plan(medications: list[Medication], plan: DailyPlan, source: str) -> int:
    """
    Persists one generate_daily_plan() call as an immutable PlanLog row.

    `source` should be "structured" (from /api/plan) or "natural_language"
    (from /api/plan/nl), so logs are queryable by entry point later.

    Returns the new row's id. Never raises on its own logic -- a failed
    log write should not be allowed to break a successful plan response,
    so callers should treat this as best-effort (see routes/api.py).
    """
    row = PlanLog(
        source=source,
        input_medications=[_medication_to_dict(m) for m in medications],
        entries=[_entry_to_dict(e) for e in plan.entries],
        warnings=[_interaction_to_dict(w) for w in plan.warnings],
        goal_trace=list(plan.goal_trace),
    )

    with get_session() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_recent_plans(limit: int = 20) -> list[dict]:
    """Returns the most recent PlanLog rows as plain dicts, newest first."""
    with get_session() as session:
        rows = (
            session.query(PlanLog)
            .order_by(PlanLog.created_at.desc())
            .limit(limit)
            .all()
        )
        return [_row_to_dict(row) for row in rows]


# -- typed dataclass -> JSON-serializable dict --------------------------------


def _medication_to_dict(medication: Medication) -> dict:
    data = asdict(medication)
    data["timing_preference"] = medication.timing_preference.value
    return data


def _entry_to_dict(entry) -> dict:
    return {
        "medication": entry.medication,
        "scheduled_time": entry.scheduled_time.strftime("%H:%M"),
        "reasoning": entry.reasoning,
        "constraint_ids": entry.constraint_ids,
    }


def _interaction_to_dict(interaction) -> dict:
    data = asdict(interaction)
    data["severity"] = interaction.severity.value
    return data


def _row_to_dict(row: PlanLog) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat(),
        "source": row.source,
        "input_medications": row.input_medications,
        "entries": row.entries,
        "warnings": row.warnings,
        "goal_trace": row.goal_trace,
    }