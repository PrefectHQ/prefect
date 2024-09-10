from typing import List, Optional, Sequence, Union
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

import prefect.server.schemas as schemas
from prefect._internal.compatibility.deprecated import deprecated_parameter
from prefect.server.database import orm_models
from prefect.server.database.dependencies import db_injector
from prefect.server.database.interface import PrefectDBInterface


def greatest(
    db: PrefectDBInterface, clamped_value: int, sql_value: ColumnElement
) -> ColumnElement:
    # Determine the greatest value based on the database type
    if db.dialect.name == "sqlite":
        # `sa.func.greatest` isn't available in SQLite, fallback to using a
        # `case` statement.
        return sa.case((clamped_value > sql_value, clamped_value), else_=sql_value)
    else:
        return sa.func.greatest(clamped_value, sql_value)


def seconds_ago(db: PrefectDBInterface, field: ColumnElement) -> ColumnElement:
    if db.dialect.name == "sqlite":
        # `sa.func.timezone` isn't available in SQLite, fallback to using
        # `julianday` .
        return (sa.func.julianday("now") - sa.func.julianday(field)) * 86400.0
    else:
        return sa.func.extract(
            "epoch",
            sa.func.timezone("UTC", sa.func.now()) - sa.func.timezone("UTC", field),
        ).cast(sa.Float)


def active_slots_after_decay(db: PrefectDBInterface) -> ColumnElement[float]:
    # Active slots will decay at a rate of `slot_decay_per_second` per second.
    return greatest(
        db,
        0,
        orm_models.ConcurrencyLimitV2.active_slots
        - sa.func.floor(
            orm_models.ConcurrencyLimitV2.slot_decay_per_second
            * seconds_ago(db, orm_models.ConcurrencyLimitV2.updated)
        ),
    )


def denied_slots_after_decay(db: PrefectDBInterface) -> ColumnElement[float]:
    # Denied slots decay at a rate of `slot_decay_per_second` per second if it's
    # greater than 0, otherwise it decays at a rate of `avg_slot_occupancy_seconds`.
    # The combination of `denied_slots` and `slot_decay_per_second` /
    # `avg_slot_occupancy_seconds` is used to by the API to give a best guess at
    # when slots will be available again.
    return greatest(
        db,
        0,
        orm_models.ConcurrencyLimitV2.denied_slots
        - sa.func.floor(
            sa.case(
                (
                    orm_models.ConcurrencyLimitV2.slot_decay_per_second > 0.0,
                    orm_models.ConcurrencyLimitV2.slot_decay_per_second,
                ),
                else_=(
                    1.0
                    / sa.cast(
                        orm_models.ConcurrencyLimitV2.avg_slot_occupancy_seconds,
                        sa.Float,
                    )
                ),
            )
            * seconds_ago(db, orm_models.ConcurrencyLimitV2.updated)
        ),
    )


# OCCUPANCY_SAMPLES_MULTIPLIER is used to determine how many samples to use when
# calculating the average occupancy seconds per slot.
OCCUPANCY_SAMPLES_MULTIPLIER = 2

# MINIMUM_OCCUPANCY_SECONDS_PER_SLOT is used to prevent the average occupancy
# from dropping too low and causing divide by zero errors.
MINIMUM_OCCUPANCY_SECONDS_PER_SLOT = 0.1


async def create_concurrency_limit(
    session: AsyncSession,
    concurrency_limit: Union[
        schemas.actions.ConcurrencyLimitV2Create, schemas.core.ConcurrencyLimitV2
    ],
) -> orm_models.ConcurrencyLimitV2:
    model = orm_models.ConcurrencyLimitV2(**concurrency_limit.model_dump())

    session.add(model)
    await session.flush()

    return model


async def read_concurrency_limit(
    session: AsyncSession,
    concurrency_limit_id: Optional[UUID] = None,
    name: Optional[str] = None,
) -> Union[orm_models.ConcurrencyLimitV2, None]:
    if not concurrency_limit_id and not name:
        raise ValueError("Must provide either concurrency_limit_id or name")

    where = (
        orm_models.ConcurrencyLimitV2.id == concurrency_limit_id
        if concurrency_limit_id
        else orm_models.ConcurrencyLimitV2.name == name
    )
    query = sa.select(orm_models.ConcurrencyLimitV2).where(where)
    result = await session.execute(query)
    return result.scalar()


async def read_all_concurrency_limits(
    session: AsyncSession,
    limit: int,
    offset: int,
) -> Sequence[orm_models.ConcurrencyLimitV2]:
    query = sa.select(orm_models.ConcurrencyLimitV2).order_by(
        orm_models.ConcurrencyLimitV2.name
    )

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


async def update_concurrency_limit(
    session: AsyncSession,
    concurrency_limit: schemas.actions.ConcurrencyLimitV2Update,
    concurrency_limit_id: Optional[UUID] = None,
    name: Optional[str] = None,
) -> bool:
    current_concurrency_limit = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit_id, name=name
    )
    if not current_concurrency_limit:
        return False

    if not concurrency_limit_id and not name:
        raise ValueError("Must provide either concurrency_limit_id or name")

    where = (
        orm_models.ConcurrencyLimitV2.id == concurrency_limit_id
        if concurrency_limit_id
        else orm_models.ConcurrencyLimitV2.name == name
    )

    result = await session.execute(
        sa.update(orm_models.ConcurrencyLimitV2)
        .where(where)
        .values(**concurrency_limit.model_dump(exclude_unset=True))
    )

    return result.rowcount > 0


async def delete_concurrency_limit(
    session: AsyncSession,
    concurrency_limit_id: Optional[UUID] = None,
    name: Optional[str] = None,
) -> bool:
    if not concurrency_limit_id and not name:
        raise ValueError("Must provide either concurrency_limit_id or name")

    where = (
        orm_models.ConcurrencyLimitV2.id == concurrency_limit_id
        if concurrency_limit_id
        else orm_models.ConcurrencyLimitV2.name == name
    )
    query = sa.delete(orm_models.ConcurrencyLimitV2).where(where)

    result = await session.execute(query)
    return result.rowcount > 0


@deprecated_parameter(
    name="create_if_missing",
    start_date="Sep 2024",
    end_date="Oct 2024",
    when=lambda x: x is not None,
    help="Limits must be explicitly created before acquiring concurrency slots.",
)
async def bulk_read_or_create_concurrency_limits(
    session: AsyncSession,
    names: List[str],
    create_if_missing: Optional[bool] = None,
) -> List[orm_models.ConcurrencyLimitV2]:
    # Get all existing concurrency limits in `names`.
    existing_query = sa.select(orm_models.ConcurrencyLimitV2).where(
        orm_models.ConcurrencyLimitV2.name.in_(names)
    )
    existing_limits = list((await session.execute(existing_query)).scalars().all())

    # If any limits aren't present in the database, create them as inactive,
    # unless we've been told not to.
    missing_names = set(names) - {str(limit.name) for limit in existing_limits}

    if missing_names and create_if_missing:
        new_limits = [
            orm_models.ConcurrencyLimitV2(
                **schemas.core.ConcurrencyLimitV2(
                    name=name, limit=1, active=False
                ).model_dump()
            )
            for name in missing_names
        ]
        session.add_all(new_limits)
        await session.flush()

        existing_limits += new_limits

    return existing_limits


@db_injector
async def bulk_increment_active_slots(
    db: PrefectDBInterface,
    session: AsyncSession,
    concurrency_limit_ids: List[UUID],
    slots: int,
) -> bool:
    active_slots = active_slots_after_decay(db)
    denied_slots = denied_slots_after_decay(db)

    query = (
        sa.update(orm_models.ConcurrencyLimitV2)
        .where(
            sa.and_(
                orm_models.ConcurrencyLimitV2.id.in_(concurrency_limit_ids),
                orm_models.ConcurrencyLimitV2.active == True,  # noqa
                active_slots + slots <= orm_models.ConcurrencyLimitV2.limit,
            )
        )
        .values(
            active_slots=active_slots + slots,
            denied_slots=denied_slots,
        )
    ).execution_options(synchronize_session=False)

    result = await session.execute(query)
    return result.rowcount == len(concurrency_limit_ids)


@db_injector
async def bulk_decrement_active_slots(
    db: PrefectDBInterface,
    session: AsyncSession,
    concurrency_limit_ids: List[UUID],
    slots: int,
    occupancy_seconds: Optional[float] = None,
) -> bool:
    query = (
        sa.update(orm_models.ConcurrencyLimitV2)
        .where(
            sa.and_(
                orm_models.ConcurrencyLimitV2.id.in_(concurrency_limit_ids),
                orm_models.ConcurrencyLimitV2.active == True,  # noqa
            )
        )
        .values(
            active_slots=sa.case(
                (
                    active_slots_after_decay(db) - slots < 0,
                    0,
                ),
                else_=active_slots_after_decay(db) - slots,
            ),
            denied_slots=denied_slots_after_decay(db),
        )
    )

    if occupancy_seconds:
        occupancy_seconds_per_slot = max(
            occupancy_seconds / slots, MINIMUM_OCCUPANCY_SECONDS_PER_SLOT
        )

        query = query.values(
            # Update the average occupancy seconds per slot as a weighted
            # average over the last `limit * OCCUPANCY_SAMPLE_MULTIPLIER` samples.
            avg_slot_occupancy_seconds=orm_models.ConcurrencyLimitV2.avg_slot_occupancy_seconds
            + (
                occupancy_seconds_per_slot
                / (orm_models.ConcurrencyLimitV2.limit * OCCUPANCY_SAMPLES_MULTIPLIER)
            )
            - (
                orm_models.ConcurrencyLimitV2.avg_slot_occupancy_seconds
                / (orm_models.ConcurrencyLimitV2.limit * OCCUPANCY_SAMPLES_MULTIPLIER)
            ),
        )

    result = await session.execute(query)
    return result.rowcount == len(concurrency_limit_ids)


@db_injector
async def bulk_update_denied_slots(
    db: PrefectDBInterface,
    session: AsyncSession,
    concurrency_limit_ids: List[UUID],
    slots: int,
) -> bool:
    query = (
        sa.update(orm_models.ConcurrencyLimitV2)
        .where(
            sa.and_(
                orm_models.ConcurrencyLimitV2.id.in_(concurrency_limit_ids),
                orm_models.ConcurrencyLimitV2.active == True,  # noqa
            )
        )
        .values(denied_slots=denied_slots_after_decay(db) + slots)
    )

    result = await session.execute(query)
    return result.rowcount == len(concurrency_limit_ids)
