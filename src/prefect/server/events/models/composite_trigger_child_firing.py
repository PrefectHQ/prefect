from typing import TYPE_CHECKING, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database import PrefectDBInterface, db_injector
from prefect.server.events.schemas.automations import CompositeTrigger, Firing
from prefect.types._datetime import DateTime, now

if TYPE_CHECKING:
    from prefect.server.database.orm_models import ORMCompositeTriggerChildFiring


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
) -> None:
    await session.execute(
        sa.delete(db.CompositeTriggerChildFiring).filter(
            db.CompositeTriggerChildFiring.automation_id == trigger.automation.id,
            db.CompositeTriggerChildFiring.parent_trigger_id == trigger.id,
            db.CompositeTriggerChildFiring.child_firing_id.in_(firing_ids),
        )
    )
