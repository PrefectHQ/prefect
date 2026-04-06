"""Backfill explicit DTSTART on existing RRule schedules

Revision ID: b893a2b346b8
Revises: 09a9e091e578
Create Date: 2026-04-06 12:00:00.000000

Closes PrefectHQ/prefect#21362.

Historically, `RRuleSchedule.to_rrule()` fell back to a hardcoded
`DEFAULT_ANCHOR_DATE = 2020-01-01` whenever the persisted rrule string
lacked an explicit `DTSTART`. dateutil's `xafter()` is O(n) in the number
of occurrences between `dtstart` and the query time, so a 5-minute rule
walks ~660k occurrences from 2020 forward on every scheduler loop,
saturating CPU when several such schedules are active.

The fix is to make `DTSTART` explicit on every persisted rrule. This
migration walks every row in `deployment_schedule` whose rrule string
lacks `DTSTART` and injects one via `normalize_rrule_string`. For
`FREQ=SECONDLY` / `FREQ=MINUTELY` rules without `COUNT`, the helper
picks a phase-equivalent recent anchor (small dateutil cache). For
every other shape, it injects the legacy `DTSTART:20200101T000000` to
preserve byte-for-byte semantics.
"""

import json
import logging

import sqlalchemy as sa
from alembic import op

from prefect._internal.schemas.validators import normalize_rrule_string

# revision identifiers, used by Alembic.
revision = "b893a2b346b8"
down_revision = "09a9e091e578"
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
            # PostgreSQL JSONB returns dict; defensive parse if it's text.
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
                    "UPDATE deployment_schedule "
                    "SET schedule = CAST(:schedule AS JSONB) WHERE id = :id"
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
    is semantically equivalent to the pre-upgrade state. Reversing the
    backfill row-by-row would require remembering which rows we touched,
    which we deliberately don't track.
    """
