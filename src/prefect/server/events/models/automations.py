from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator, Optional, Sequence, Union
from uuid import UUID

import pendulum
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.events import filters
from prefect.server.events.schemas.automations import (
    Automation,
    AutomationPartialUpdate,
    AutomationSort,
    AutomationUpdate,
)
from prefect.settings import PREFECT_API_SERVICES_TRIGGERS_ENABLED
from prefect.utilities.asyncutils import run_coro_as_sync

if TYPE_CHECKING:
    from prefect.server.database import orm_models


@asynccontextmanager
@db_injector
async def automations_session(
    db: PrefectDBInterface, begin_transaction: bool = False
) -> AsyncGenerator[AsyncSession, None]:
    async with db.session_context(begin_transaction=begin_transaction) as session:
        yield session


@db_injector
async def read_automations_for_workspace(
    db: PrefectDBInterface,
    session: AsyncSession,
    sort: AutomationSort = AutomationSort.NAME_ASC,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    automation_filter: Optional[filters.AutomationFilter] = None,
) -> Sequence[Automation]:
    query = sa.select(db.Automation)

    query = query.order_by(db.Automation.sort_expression(sort))

    if automation_filter:
        query = query.where(automation_filter.as_sql_filter())
    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)

    result = await session.execute(query)

    return [
        Automation.model_validate(a, from_attributes=True)
        for a in result.scalars().all()
    ]


@db_injector
async def count_automations_for_workspace(
    db: PrefectDBInterface,
    session: AsyncSession,
) -> int:
    query = sa.select(sa.func.count(sa.text("*"))).select_from(db.Automation)

    result = await session.execute(query)

    return result.scalar() or 0


@db_injector
async def read_automation(
    db: PrefectDBInterface,
    session: AsyncSession,
    automation_id: UUID,
) -> Optional[Automation]:
    result = await session.execute(
        sa.select(db.Automation).where(db.Automation.id == automation_id)
    )
    automation: Optional[orm_models.Automation] = result.scalars().first()
    if not automation:
        return None
    return Automation.model_validate(automation, from_attributes=True)


@db_injector
async def read_automation_by_id(
    db: PrefectDBInterface, session: AsyncSession, automation_id: UUID
) -> Optional[Automation]:
    result = await session.execute(
        sa.select(db.Automation).where(
            db.Automation.id == automation_id,
        )
    )
    automation: Optional[orm_models.Automation] = result.scalars().first()
    if not automation:
        return None
    return Automation.model_validate(automation, from_attributes=True)


async def _notify(session: AsyncSession, automation: Automation, event: str):
    if not PREFECT_API_SERVICES_TRIGGERS_ENABLED:
        return

    from prefect.server.events.triggers import automation_changed

    sync_session = session.sync_session

    def change_notification(session, **kwargs):
        try:
            run_coro_as_sync(automation_changed(automation.id, f"automation__{event}"))
        except Exception:
            # On exception, do not re-raise, just move on
            pass

    sa.event.listen(sync_session, "after_commit", change_notification, once=True)


@db_injector
async def create_automation(
    db: PrefectDBInterface, session: AsyncSession, automation: Automation
) -> Automation:
    new_automation = db.Automation(**automation.model_dump())
    session.add(new_automation)
    await session.flush()
    automation = Automation.model_validate(new_automation, from_attributes=True)

    await _sync_automation_related_resources(session, new_automation.id, automation)

    await _notify(session, automation, "created")
    return automation


@db_injector
async def update_automation(
    db: PrefectDBInterface,
    session: AsyncSession,
    automation_update: Union[AutomationUpdate, AutomationPartialUpdate],
    automation_id: UUID,
) -> bool:
    if not isinstance(automation_update, (AutomationUpdate, AutomationPartialUpdate)):
        raise TypeError(
            "automation_update must be an AutomationUpdate or AutomationPartialUpdate, "
            f"not {type(automation_update)}"
        )

    automation = await read_automation(session, automation_id)
    if not automation:
        return False

    if isinstance(automation_update, AutomationPartialUpdate):
        # Partial updates won't go through the full Automation/AutomationCore
        # validation, which could change due to one of these updates.  Here we attempt
        # to apply and parse the final effect of the partial update to the existing
        # automation to see if anything fails validation.
        Automation.model_validate(
            {
                **automation.model_dump(mode="json"),
                **automation_update.model_dump(mode="json"),
            }
        )

    result = await session.execute(
        sa.update(db.Automation)
        .where(db.Automation.id == automation_id)
        .values(**automation_update.model_dump_for_orm(exclude_unset=True))
    )

    if isinstance(automation_update, AutomationUpdate):
        await _sync_automation_related_resources(
            session, automation_id, automation_update
        )

    await _notify(session, automation, "updated")
    return result.rowcount > 0  # type: ignore


@db_injector
async def delete_automation(
    db: PrefectDBInterface,
    session: AsyncSession,
    automation_id: UUID,
) -> bool:
    automation = await read_automation(session, automation_id)
    if not automation:
        return False

    await session.execute(
        sa.delete(db.Automation).where(
            db.Automation.id == automation_id,
        )
    )
    await _sync_automation_related_resources(session, automation_id, None)

    await _notify(session, automation, "deleted")
    return True


@db_injector
async def delete_automations_for_workspace(
    db: PrefectDBInterface,
    session: AsyncSession,
) -> bool:
    automations = await read_automations_for_workspace(
        session,
    )
    result = await session.execute(sa.delete(db.Automation))
    for automation in automations:
        await _notify(session, automation, "deleted")
    return result.rowcount > 0


@db_injector
async def disable_automations_for_workspace(
    db: PrefectDBInterface,
    session: AsyncSession,
) -> bool:
    automations = await read_automations_for_workspace(session)
    result = await session.execute(sa.update(db.Automation).values(enabled=False))
    for automation in automations:
        await _notify(session, automation, "updated")
    return result.rowcount > 0


@db_injector
async def disable_automation(
    db: PrefectDBInterface, session: AsyncSession, automation_id: UUID
) -> bool:
    automation = await read_automation_by_id(
        session=session,
        automation_id=automation_id,
    )
    if not automation:
        raise ValueError(f"Automation with ID {automation_id} not found")

    result = await session.execute(
        sa.update(db.Automation)
        .where(db.Automation.id == automation_id)
        .values(enabled=False)
    )
    await _notify(session, automation, "updated")
    return result.rowcount > 0


@db_injector
async def _sync_automation_related_resources(
    db: PrefectDBInterface,
    session: AsyncSession,
    automation_id: UUID,
    automation: Optional[Union[Automation, AutomationUpdate]],
):
    """Actively maintains the set of related resources for an automation"""
    from prefect.server.events import actions

    await session.execute(
        sa.delete(db.AutomationRelatedResource).where(
            db.AutomationRelatedResource.automation_id == automation_id,
            db.AutomationRelatedResource.resource_id.like("prefect.deployment.%"),
            db.AutomationRelatedResource.automation_owned_by_resource.is_(False),
        ),
        execution_options={"synchronize_session": False},
    )

    if not automation:
        return

    deployment_ids = set(
        action.deployment_id
        for action in automation.actions
        if isinstance(action, actions.RunDeployment) and action.source == "selected"
    )
    for deployment_id in deployment_ids:
        await relate_automation_to_resource(
            session, automation_id, f"prefect.deployment.{deployment_id}", False
        )


@db_injector
async def relate_automation_to_resource(
    db: PrefectDBInterface,
    session: AsyncSession,
    automation_id: UUID,
    resource_id: str,
    owned_by_resource: bool,
) -> None:
    await session.execute(
        db.insert(db.AutomationRelatedResource)
        .values(
            automation_id=automation_id,
            resource_id=resource_id,
            automation_owned_by_resource=owned_by_resource,
        )
        .on_conflict_do_update(
            index_elements=[
                db.AutomationRelatedResource.automation_id,
                db.AutomationRelatedResource.resource_id,
            ],
            set_=dict(
                automation_owned_by_resource=sa.or_(
                    db.AutomationRelatedResource.automation_owned_by_resource,
                    sa.true() if owned_by_resource else sa.false(),
                ),
                updated=pendulum.now("UTC"),
            ),
        )
    )


@db_injector
async def read_automations_related_to_resource(
    db: PrefectDBInterface,
    session: AsyncSession,
    resource_id: str,
    owned_by_resource: Optional[bool] = None,
    automation_filter: Optional[filters.AutomationFilter] = None,
) -> Sequence[Automation]:
    query = (
        sa.select(db.Automation)
        .join(db.Automation.related_resources)
        .where(
            db.AutomationRelatedResource.resource_id == resource_id,
        )
    )
    if owned_by_resource is not None:
        query = query.where(
            db.AutomationRelatedResource.automation_owned_by_resource
            == owned_by_resource
        )

    if automation_filter:
        query = query.where(automation_filter.as_sql_filter())

    result = await session.execute(query)
    return [
        Automation.model_validate(a, from_attributes=True)
        for a in result.scalars().all()
    ]


@db_injector
async def delete_automations_owned_by_resource(
    db: PrefectDBInterface,
    session: AsyncSession,
    resource_id: str,
    automation_filter: Optional[filters.AutomationFilter] = None,
) -> Sequence[UUID]:
    automations = await read_automations_related_to_resource(
        session=session,
        resource_id=resource_id,
        owned_by_resource=True,
        automation_filter=automation_filter,
    )

    automation_ids = [automation.id for automation in automations]

    await session.execute(
        sa.delete(db.Automation).where(db.Automation.id.in_(automation_ids))
    )

    for automation in automations:
        await _notify(session, automation, "deleted")

    return automation_ids
