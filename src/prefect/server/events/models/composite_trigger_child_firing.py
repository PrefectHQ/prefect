from typing import TYPE_CHECKING, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events.schemas.automations import CompositeTrigger, Firing
from prefect.server.utilities.database import get_dialect
from prefect.types._datetime import DateTime, now

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMCompositeTriggerChildFiring


async def acquire_composite_trigger_lock(
    session: AsyncSession,
    trigger: CompositeTrigger,
) -> None:
    """
    Acquire a transaction-scoped advisory lock for the given composite trigger.

    This serializes concurrent child trigger evaluations for the same compound
    trigger, preventing a race condition where multiple transactions each see
    only their own child firing and neither fires the parent.

    The lock is automatically released when the transaction commits or rolls back.
    """
    bind = session.get_bind()
    if bind is None:
        return

    # Get the engine from either an Engine or Connection
    engine: sa.Engine = bind if isinstance(bind, sa.Engine) else bind.engine  # type: ignore[union-attr]
    dialect = get_dialect(engine)

    if dialect.name == "postgresql":
        # Use the trigger's UUID as the lock key
        # pg_advisory_xact_lock takes a bigint, so we use the UUID's int representation
        # truncated to fit (collision is extremely unlikely and benign)
        lock_key = int(trigger.id) % (2**63)
        await session.execute(
            sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key}
        )
    # SQLite doesn't support advisory locks, but SQLite also serializes writes
    # at the database level, so the race condition is less likely to occur


@db_injector
async def upsert_child_firing(
    db: PrefectDBInterface,
    session: AsyncSession,
    firing: Firing,
):
    automation_id = firing.trigger.automation.id
    parent_trigger_id = firing.trigger.parent.id
    child_trigger_id = firing.trigger.id

    upsert = (
        postgresql.insert(db.CompositeTriggerChildFiring)
        .values(
            automation_id=automation_id,
            parent_trigger_id=parent_trigger_id,
            child_trigger_id=child_trigger_id,
            child_firing_id=firing.id,
            child_fired_at=firing.triggered,
            child_firing=firing.model_dump(),
        )
        .on_conflict_do_update(
            index_elements=[
                db.CompositeTriggerChildFiring.automation_id,
                db.CompositeTriggerChildFiring.parent_trigger_id,
                db.CompositeTriggerChildFiring.child_trigger_id,
            ],
            set_=dict(
                child_firing_id=firing.id,
                child_fired_at=firing.triggered,
                child_firing=firing.model_dump(),
                updated=now("UTC"),
            ),
        )
    )

    await session.execute(upsert)

    result = await session.execute(
        sa.select(db.CompositeTriggerChildFiring).filter(
            db.CompositeTriggerChildFiring.automation_id == automation_id,
            db.CompositeTriggerChildFiring.parent_trigger_id == parent_trigger_id,
            db.CompositeTriggerChildFiring.child_trigger_id == child_trigger_id,
        )
    )

    return result.scalars().one()


@db_injector
async def get_child_firings(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: CompositeTrigger,
) -> Sequence["ORMCompositeTriggerChildFiring"]:
    result = await session.execute(
        sa.select(db.CompositeTriggerChildFiring).filter(
            db.CompositeTriggerChildFiring.automation_id == trigger.automation.id,
            db.CompositeTriggerChildFiring.parent_trigger_id == trigger.id,
            db.CompositeTriggerChildFiring.child_trigger_id.in_(
                trigger.child_trigger_ids
            ),
        )
    )

    return result.scalars().unique().all()


@db_injector
async def clear_old_child_firings(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: CompositeTrigger,
    fired_before: DateTime,
) -> None:
    await session.execute(
        sa.delete(db.CompositeTriggerChildFiring).filter(
            db.CompositeTriggerChildFiring.automation_id == trigger.automation.id,
            db.CompositeTriggerChildFiring.parent_trigger_id == trigger.id,
            db.CompositeTriggerChildFiring.child_fired_at < fired_before,
        )
    )


@db_injector
async def clear_child_firings(
    db: PrefectDBInterface,
    session: AsyncSession,
    trigger: CompositeTrigger,
    firing_ids: Sequence[UUID],
) -> set[UUID]:
    """
    Delete the specified child firings and return the IDs that were actually deleted.

    Returns the set of child_firing_ids that were successfully deleted. Callers can
    compare this to the expected firing_ids to detect races and avoid double-firing
    composite triggers.
    """
    result = await session.execute(
        sa.delete(db.CompositeTriggerChildFiring)
        .filter(
            db.CompositeTriggerChildFiring.automation_id == trigger.automation.id,
            db.CompositeTriggerChildFiring.parent_trigger_id == trigger.id,
            db.CompositeTriggerChildFiring.child_firing_id.in_(firing_ids),
        )
        .returning(db.CompositeTriggerChildFiring.child_firing_id)
    )

    return set(result.scalars().all())
