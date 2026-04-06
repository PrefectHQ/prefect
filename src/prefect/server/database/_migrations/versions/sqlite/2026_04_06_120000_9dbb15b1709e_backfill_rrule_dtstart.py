"""Backfill explicit DTSTART on existing RRule schedules

Revision ID: 9dbb15b1709e
Revises: 4dfa692e02a7
Create Date: 2026-04-06 12:00:00.000000

Closes PrefectHQ/prefect#21362.

See the PostgreSQL twin (`b893a2b346b8`) for the full rationale. Same
behavior, different SQL: SQLite stores the `schedule` column as JSON
text rather than JSONB, so we read/write it as a string and skip the
explicit cast.
"""

import json
import logging

import sqlalchemy as sa
from alembic import op

from prefect._internal.schemas.validators import normalize_rrule_string

# revision identifiers, used by Alembic.
revision = "9dbb15b1709e"
down_revision = "4dfa692e02a7"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def upgrade():
    connection = op.get_bind()

    rows = connection.execute(
        sa.text("SELECT id, schedule FROM deployment_schedule")
    ).fetchall()

    for row in rows:
        try:
            schedule = row.schedule
            if isinstance(schedule, str):
                schedule = json.loads(schedule)
            if not isinstance(schedule, dict):
                continue

            rrule = schedule.get("rrule")
            if not isinstance(rrule, str) or not rrule:
                continue
            if "DTSTART" in rrule.upper():
                continue

            normalized = normalize_rrule_string(rrule)
            if normalized == rrule:
                continue

            schedule["rrule"] = normalized
            connection.execute(
                sa.text(
                    "UPDATE deployment_schedule SET schedule = :schedule WHERE id = :id"
                ),
                {"id": str(row.id), "schedule": json.dumps(schedule)},
            )
        except Exception as exc:
            # A single pathological row should not abort the whole
            # backfill. Log and continue; the row keeps its original
            # (un-normalized) value and the scheduler will continue to
            # use the legacy 2020 anchor for it.
            logger.warning(
                "Skipping deployment_schedule row %s during DTSTART backfill: %s",
                getattr(row, "id", "<unknown>"),
                exc,
            )


def downgrade():
    """Downgrade is a no-op.

    The injected `DTSTART` lines produce occurrence sets identical to
    the implicit-anchor parsing they replaced, so leaving them in place
    is semantically equivalent to the pre-upgrade state.
    """
