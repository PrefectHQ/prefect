from typing import List, Optional, Union
from uuid import UUID

import sqlalchemy as sa

import prefect.server.schemas as schemas
from prefect.server.database.dependencies import inject_db
from prefect.server.database.interface import PrefectDBInterface


def greatest(db, clamped_value, sql_value):
    # Determine the greatest value based on the database type
    if db.dialect.name == "sqlite":
        # `sa.func.greatest` isn't available in SQLite, fallback to using a
        # `case` statement.
        return sa.case((clamped_value > sql_value, clamped_value), else_=sql_value)
    else:
        return sa.func.greatest(clamped_value, sql_value)


def seconds_ago(db, field) -> float:
    if db.dialect.name == "sqlite":
        # `sa.func.timezone` isn't available in SQLite, fallback to using
        # `julianday` .
        return (sa.func.julianday("now") - sa.func.julianday(field)) * 86400.0
    else:
        return sa.func.extract(
            "epoch",
            sa.func.timezone("UTC", sa.func.now()) - sa.func.timezone("UTC", field),
        ).cast(sa.Float)


def active_slots_after_decay(db: PrefectDBInterface):
    # Active slots will decay at a rate of `slot_decay_per_second` per second.
    return greatest(
        db,
        0,
        db.ConcurrencyLimitV2.active_slots
        - sa.func.floor(
            db.ConcurrencyLimitV2.slot_decay_per_second
            * seconds_ago(db, db.ConcurrencyLimitV2.updated)
        ),
    )


def denied_slots_after_decay(db: PrefectDBInterface):
    # Denied slots decay at a rate of `slot_decay_per_second` per second if it's
    # greater than 0, otherwise it decays at a rate of `avg_slot_occupancy_seconds`.
    # The combination of `denied_slots` and `slot_decay_per_second` /
    # `avg_slot_occupancy_seconds` is used to by the API to give a best guess at
    # when slots will be available again.
    return greatest(
        db,
        0,
        db.ConcurrencyLimitV2.denied_slots
        - sa.func.floor(
            sa.case(
                (
                    db.ConcurrencyLimitV2.slot_decay_per_second > 0.0,
                    db.ConcurrencyLimitV2.slot_decay_per_second,
                ),
                else_=(
                    1.0
                    / sa.cast(
                        db.ConcurrencyLimitV2.avg_slot_occupancy_seconds, sa.Float
                    )
                ),
            )
            * seconds_ago(db, db.ConcurrencyLimitV2.updated)
        ),
    )


# OCCUPANCY_SAMPLES_MULTIPLIER is used to determine how many samples to use when
# calculating the average occupancy seconds per slot.
OCCUPANCY_SAMPLES_MULTIPLIER = 2

# MINIMUM_OCCUPANCY_SECONDS_PER_SLOT is used to prevent the average occupancy
# from dropping too low and causing divide by zero errors.
MINIMUM_OCCUPANCY_SECONDS_PER_SLOT = 0.1


@inject_db
async def create_concurrency_limit(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    concurrency_limit: Union[
        schemas.actions.ConcurrencyLimitV2Create, schemas.core.ConcurrencyLimitV2
    ],
):
    model = db.ConcurrencyLimitV2(**concurrency_limit.dict())

    session.add(model)
    await session.flush()

    return model


@inject_db
async def read_concurrency_limit(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    concurrency_limit_id: Optional[UUID] = None,
    name: Optional[str] = None,
):
    if not concurrency_limit_id and not name:
        raise ValueError("Must provide either concurrency_limit_id or name")

    where = (
        db.ConcurrencyLimitV2.id == concurrency_limit_id
        if concurrency_limit_id
        else db.ConcurrencyLimitV2.name == name
    )
    query = sa.select(db.ConcurrencyLimitV2).where(where)
    result = await session.execute(query)
    return result.scalar()


@inject_db
async def read_all_concurrency_limits(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    limit: int,
    offset: int,
):
    query = sa.select(db.ConcurrencyLimitV2).order_by(db.ConcurrencyLimitV2.name)

    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    return result.scalars().unique().all()


@inject_db
async def update_concurrency_limit(
    session: sa.orm.Session,
    db: PrefectDBInterface,
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
        db.ConcurrencyLimitV2.id == concurrency_limit_id
        if concurrency_limit_id
        else db.ConcurrencyLimitV2.name == name
    )

    result = await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(where)
        .values(**concurrency_limit.dict(exclude_unset=True))
    )

    return result.rowcount > 0


@inject_db
async def delete_concurrency_limit(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    concurrency_limit_id: Optional[UUID] = None,
    name: Optional[str] = None,
) -> bool:
    if not concurrency_limit_id and not name:
        raise ValueError("Must provide either concurrency_limit_id or name")

    where = (
        db.ConcurrencyLimitV2.id == concurrency_limit_id
        if concurrency_limit_id
        else db.ConcurrencyLimitV2.name == name
    )
    query = sa.delete(db.ConcurrencyLimitV2).where(where)

    result = await session.execute(query)
    return result.rowcount > 0


@inject_db
async def bulk_read_or_create_concurrency_limits(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    names: List[str],
):
    # Get all existing concurrency limits in `names`.
    existing_query = sa.select(db.ConcurrencyLimitV2).where(
        db.ConcurrencyLimitV2.name.in_(names)
    )
    existing_limits = list((await session.execute(existing_query)).scalars().all())

    # If any limits aren't present in the database, create them as inactive.
    missing_names = set(names) - {str(limit.name) for limit in existing_limits}

    if missing_names:
        new_limits = [
            db.ConcurrencyLimitV2(
                **schemas.core.ConcurrencyLimitV2(
                    name=name, limit=1, active=False
                ).dict()
            )
            for name in missing_names
        ]
        session.add_all(new_limits)
        await session.flush()

        existing_limits += new_limits

    return existing_limits


@inject_db
async def bulk_increment_active_slots(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    concurrency_limit_ids: List[UUID],
    slots: int,
) -> bool:
    active_slots = active_slots_after_decay(db)
    denied_slots = denied_slots_after_decay(db)

    query = (
        sa.update(db.ConcurrencyLimitV2)
        .where(
            sa.and_(
                db.ConcurrencyLimitV2.id.in_(concurrency_limit_ids),
                db.ConcurrencyLimitV2.active == True,  # noqa
                active_slots + slots <= db.ConcurrencyLimitV2.limit,
            )
        )
        .values(
            active_slots=active_slots + slots,
            denied_slots=denied_slots,
        )
    ).execution_options(synchronize_session=False)

    result = await session.execute(query)
    return result.rowcount == len(concurrency_limit_ids)


@inject_db
async def bulk_decrement_active_slots(
    session: sa.orm.Session,
    db: PrefectDBInterface,
    concurrency_limit_ids: List[UUID],
    slots: int,
    occupancy_seconds: Optional[float] = None,
) -> bool:
    query = (
        sa.update(db.ConcurrencyLimitV2)
        .where(
            sa.and_(
                db.ConcurrencyLimitV2.id.in_(concurrency_limit_ids),
                db.ConcurrencyLimitV2.active == True,  # noqa
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
            avg_slot_occupancy_seconds=db.ConcurrencyLimitV2.avg_slot_occupancy_seconds
            + (
                occupancy_seconds_per_slot
                / (db.ConcurrencyLimitV2.limit * OCCUPANCY_SAMPLES_MULTIPLIER)
            )
            - (
                db.ConcurrencyLimitV2.avg_slot_occupancy_seconds
                / (db.ConcurrencyLimitV2.limit * OCCUPANCY_SAMPLES_MULTIPLIER)
            ),
        )

    result = await session.execute(query)
    return result.rowcount == len(concurrency_limit_ids)


@inject_db
async def bulk_update_denied_slots(
    session: sa.orm.Session,
    concurrency_limit_ids: List[UUID],
    slots: int,
    db: PrefectDBInterface,
):
    query = (
        sa.update(db.ConcurrencyLimitV2)
        .where(
            sa.and_(
                db.ConcurrencyLimitV2.id.in_(concurrency_limit_ids),
                db.ConcurrencyLimitV2.active == True,  # noqa
            )
        )
        .values(denied_slots=denied_slots_after_decay(db) + slots)
    )

    result = await session.execute(query)
    return result.rowcount == len(concurrency_limit_ids)
