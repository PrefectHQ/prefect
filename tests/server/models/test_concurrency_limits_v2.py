import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
import sqlalchemy as sa
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server import models, schemas
from prefect.server.database import PrefectDBInterface
from prefect.server.models.concurrency_limits_v2 import (
    MINIMUM_OCCUPANCY_SECONDS_PER_SLOT,
    bulk_decrement_active_slots,
    bulk_increment_active_slots,
    bulk_read_concurrency_limits,
    bulk_update_denied_slots,
    create_concurrency_limit,
    delete_concurrency_limit,
    denied_slots_after_decay,
    read_all_concurrency_limits,
    read_concurrency_limit,
    update_concurrency_limit,
)
from prefect.server.schemas.actions import (
    ConcurrencyLimitV2Create,
    ConcurrencyLimitV2Update,
)
from prefect.server.schemas.core import ConcurrencyLimitV2


@pytest.fixture
async def concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test_limit",
            limit=10,
            avg_slot_occupancy_seconds=0.5,
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def concurrency_limit_with_decay(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test_limit_with_decay",
            limit=10,
            slot_decay_per_second=10.0,
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def locked_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="locked_limit",
            limit=10,
            active_slots=10,
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


async def test_create_concurrency_limit(session: AsyncSession):
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test_limit",
            limit=10,
            slot_decay_per_second=0.5,
        ),
    )

    assert concurrency_limit.id is not None
    assert concurrency_limit.active
    assert concurrency_limit.name == "test_limit"
    assert concurrency_limit.limit == 10
    assert concurrency_limit.slot_decay_per_second == 0.5


async def test_create_concurrency_limit_with_invalid_name_raises(session: AsyncSession):
    with pytest.raises(ValidationError, match="String should match pattern"):
        await create_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2(
                name="test_limit & 0 < 1",
                limit=10,
                slot_decay_per_second=0.5,
            ),
        )


async def test_create_concurrency_limit_with_invalid_limit_raises(
    session: AsyncSession,
):
    with pytest.raises(
        ValidationError,
        match=" Input should be greater than or equal to 0",
    ):
        await create_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2Create(
                name="test_limit",
                limit=-2,
                slot_decay_per_second=0.5,
            ),
        )


async def test_create_concurrency_limit_with_invalid_slot_decay_raises(
    session: AsyncSession,
):
    with pytest.raises(
        ValidationError,
        match=" Input should be greater than or equal to 0",
    ):
        await create_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2Create(
                name="test_limit",
                limit=10,
                slot_decay_per_second=-1,
            ),
        )


async def test_create_concurrency_limit_with_duplicate_name_raises(
    session: AsyncSession,
):
    await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="test_limit", limit=10),
    )

    with pytest.raises(IntegrityError):
        await create_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2(name="test_limit", limit=10),
        )


async def test_read_concurrency_limit_by_id(
    session: AsyncSession, concurrency_limit: ConcurrencyLimitV2
):
    fetched = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )

    assert fetched
    assert fetched.id == concurrency_limit.id


async def test_read_concurrency_limit_by_name(
    session: AsyncSession, concurrency_limit: ConcurrencyLimitV2
):
    fetched = await read_concurrency_limit(session, name=concurrency_limit.name)

    assert fetched
    assert fetched.id == concurrency_limit.id


async def test_read_all_concurrency_limits(
    session: AsyncSession,
    concurrency_limit: ConcurrencyLimitV2,
    locked_concurrency_limit: ConcurrencyLimitV2,
    concurrency_limit_with_decay: ConcurrencyLimitV2,
):
    concurrency_limits = await read_all_concurrency_limits(session, limit=10, offset=0)

    assert list(limit.name for limit in concurrency_limits) == [
        "locked_limit",
        "test_limit",
        "test_limit_with_decay",
    ]


async def test_read_all_concurrency_limits_respects_limit_and_offset(
    concurrency_limit: ConcurrencyLimitV2,
    locked_concurrency_limit: ConcurrencyLimitV2,
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    session: AsyncSession,
):
    concurrency_limits = await read_all_concurrency_limits(session, limit=1, offset=0)

    # Limits are sorted by name, so the first limit should be "locked_limit"
    assert len(concurrency_limits) == 1
    assert str(concurrency_limits[0].name) == "locked_limit"

    concurrency_limits = await read_all_concurrency_limits(session, limit=1, offset=1)

    # The second limit should be "test_limit"
    assert len(concurrency_limits) == 1
    assert str(concurrency_limits[0].name) == "test_limit"


async def test_update_concurrency_limit_by_id(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    await update_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2Update(name="new-name"),
        concurrency_limit_id=concurrency_limit.id,
    )
    await session.commit()

    refreshed = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )

    assert refreshed
    assert refreshed.name == "new-name"


async def test_update_concurrency_limit_with_id_not_found(
    session: AsyncSession,
):
    assert not await update_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2Update(),
        concurrency_limit_id=UUID("00000000-0000-0000-0000-000000000000"),
    ), "Concurrency limit with id 9999 should not be found"


async def test_update_concurrency_limit_by_name(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    await update_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2Update(name="new-name"),
        name=concurrency_limit.name,
    )
    await session.commit()

    refreshed = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )

    assert refreshed
    assert refreshed.name == "new-name"


async def test_update_concurrency_limit_with_name_not_found(
    session: AsyncSession,
):
    assert not await update_concurrency_limit(
        session=session, concurrency_limit=ConcurrencyLimitV2Update(), name="not-found"
    ), "Concurrency limit with name 'not-found' should not be found"


async def test_delete_concurrency_limit_by_id(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    assert await delete_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )
    assert not await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )


async def test_delete_concurrency_limit_used_for_deployment_concurrency_limiting(
    session: AsyncSession, deployment
):
    await models.deployments.update_deployment(
        session, deployment.id, schemas.actions.DeploymentUpdate(concurrency_limit=6)
    )
    await session.commit()
    await session.refresh(deployment)
    assert deployment.global_concurrency_limit is not None

    assert await delete_concurrency_limit(
        session, concurrency_limit_id=deployment.concurrency_limit_id
    )
    await session.commit()

    await session.refresh(deployment)
    assert deployment.global_concurrency_limit is None
    assert deployment.concurrency_limit_id is None


async def test_update_concurrency_limit_with_invalid_name_raises(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    with pytest.raises(ValidationError, match="String should match pattern"):
        await update_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2Update(name="test_limit & 0 < 1"),
            concurrency_limit_id=concurrency_limit.id,
        )


async def test_update_concurrency_limit_with_invalid_limit_raises(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    with pytest.raises(
        ValidationError,
        match=" Input should be greater than or equal to 0",
    ):
        await update_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2Update(limit=-2),
            concurrency_limit_id=concurrency_limit.id,
        )


async def test_update_concurrency_limit_with_invalid_slot_decay_raises(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    with pytest.raises(
        ValidationError,
        match=" Input should be greater than or equal to 0",
    ):
        await update_concurrency_limit(
            session=session,
            concurrency_limit=ConcurrencyLimitV2Update(slot_decay_per_second=-1),
            concurrency_limit_id=concurrency_limit.id,
        )


async def test_delete_concurrency_limit_by_name(
    concurrency_limit: ConcurrencyLimitV2, session: AsyncSession
):
    assert await delete_concurrency_limit(session, name=concurrency_limit.name)
    assert not await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )


async def test_bulk_read_concurrency_limits_default(session: AsyncSession):
    names = ["Chase", "Marshall", "Skye", "Rubble", "Zuma", "Rocky", "Everest"]

    pre_existing = names[:3]

    for name in pre_existing:
        await create_concurrency_limit(
            session=session, concurrency_limit=ConcurrencyLimitV2(name=name, limit=1)
        )

    limits = await bulk_read_concurrency_limits(session=session, names=names)

    assert set(pre_existing) == {limit.name for limit in limits}
    assert all(limit.active for limit in limits)


async def test_increment_active_slots_success(
    session: AsyncSession,
    concurrency_limit: ConcurrencyLimitV2,
):
    assert await bulk_increment_active_slots(
        session=session, concurrency_limit_ids=[concurrency_limit.id], slots=1
    )

    refreshed = await read_concurrency_limit(
        session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed
    assert refreshed.active_slots == 1


async def test_increment_active_slots_failure(
    session: AsyncSession,
    locked_concurrency_limit: ConcurrencyLimitV2,
):
    await bulk_increment_active_slots(
        session=session, concurrency_limit_ids=[locked_concurrency_limit.id], slots=1
    )

    refreshed = await read_concurrency_limit(
        session, concurrency_limit_id=locked_concurrency_limit.id
    )
    assert refreshed
    assert refreshed.active_slots == locked_concurrency_limit.limit


async def test_increment_active_slots_with_decay_success(
    session: AsyncSession,
    concurrency_limit_with_decay: ConcurrencyLimitV2,
):
    assert await bulk_increment_active_slots(
        session=session,
        concurrency_limit_ids=[concurrency_limit_with_decay.id],
        slots=1,
    )

    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit_with_decay.id
    )
    assert refreshed
    assert refreshed.active_slots == 1


async def test_increment_active_slots_with_decay_slots_decay_over_time(
    db: PrefectDBInterface,
    concurrency_limit_with_decay: ConcurrencyLimitV2,
):
    async with db.session_context() as session:
        assert await bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[concurrency_limit_with_decay.id],
            slots=10,
        )

        refreshed = await read_concurrency_limit(
            session=session, concurrency_limit_id=concurrency_limit_with_decay.id
        )
        assert refreshed
        assert refreshed.active_slots == 10

        await session.commit()

    # `concurrency_limit_with_decay` has a decay of 10.0 slots/second.
    # Immediately after filling to 10, we shouldn't be able to acquire 5 more.
    async with db.session_context() as session:
        assert not await bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[concurrency_limit_with_decay.id],
            slots=5,
        )

    # After 1 second, all 10 slots should have decayed (10 * 1.0 = 10),
    # so we should be able to acquire 5 slots.
    await asyncio.sleep(1.0)

    async with db.session_context() as session:
        assert await bulk_increment_active_slots(
            session=session,
            concurrency_limit_ids=[concurrency_limit_with_decay.id],
            slots=5,
        )


async def test_increment_active_slots_without_decay_slots_do_not_decay(
    session: AsyncSession,
    concurrency_limit: ConcurrencyLimitV2,
):
    assert await bulk_increment_active_slots(
        session=session, concurrency_limit_ids=[concurrency_limit.id], slots=10
    )

    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed
    assert refreshed.active_slots == 10

    await session.commit()

    # `concurrency_limit` has no decay, so after a sleep, the active slots
    # should be the same as before and not allow us to increment.

    assert not await bulk_increment_active_slots(
        session=session, concurrency_limit_ids=[concurrency_limit.id], slots=5
    )

    await asyncio.sleep(0.5)

    assert not await bulk_increment_active_slots(
        session=session, concurrency_limit_ids=[concurrency_limit.id], slots=5
    )


async def test_increment_active_slots_denied_slots_decay_over_time(
    session: AsyncSession,
    concurrency_limit: ConcurrencyLimitV2,
):
    assert await bulk_update_denied_slots(
        session=session, concurrency_limit_ids=[concurrency_limit.id], slots=10
    )
    await session.commit()

    assert concurrency_limit.avg_slot_occupancy_seconds == 0.5

    await asyncio.sleep(0.5)

    # The decay of `denied_slots` is calculated during updates, so we have
    # to make an update to trigger recalculation.
    assert await bulk_increment_active_slots(
        session=session, concurrency_limit_ids=[concurrency_limit.id], slots=1
    )

    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=concurrency_limit.id
    )
    assert refreshed

    # `concurrency_limit` has an avg_slot_occpancy_seconds of 0.5, so after
    # 0.5 seconds, the denied slots should be 9 (10 - 1)
    assert refreshed.denied_slots == 9


async def test_bulk_decrement_active_slots(
    session: AsyncSession,
    locked_concurrency_limit: ConcurrencyLimitV2,
):
    await bulk_decrement_active_slots(
        session=session, concurrency_limit_ids=[locked_concurrency_limit.id], slots=10
    )

    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=locked_concurrency_limit.id
    )
    assert refreshed
    assert refreshed.active_slots == 0


async def test_bulk_decrement_active_slots_clamped(
    session: AsyncSession,
    locked_concurrency_limit: ConcurrencyLimitV2,
):
    # Decrement by 100, but the active slots is 10, so it should be clamped to 0
    await bulk_decrement_active_slots(
        session=session, concurrency_limit_ids=[locked_concurrency_limit.id], slots=100
    )

    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=locked_concurrency_limit.id
    )
    assert refreshed
    assert refreshed.active_slots == 0


async def test_bulk_decrement_active_slots_updates_occupancy_seconds(
    session: AsyncSession,
    locked_concurrency_limit: ConcurrencyLimitV2,
):
    previous_value = 2.0
    for _ in range(10):
        await bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=[locked_concurrency_limit.id],
            slots=1,
            occupancy_seconds=5.0,
        )

        refreshed = await read_concurrency_limit(
            session, concurrency_limit_id=locked_concurrency_limit.id
        )
        assert refreshed

        # Since the average is set to 2.0s by default, on each iteration
        # we should expect that `avg_slot_occupancy_seconds` is closer to
        # 5.0s than the previous iteration.

        assert refreshed.avg_slot_occupancy_seconds < 5.0
        assert (5.0 - refreshed.avg_slot_occupancy_seconds) < (5.0 - previous_value)

        previous_value = refreshed.avg_slot_occupancy_seconds


async def test_bulk_decrement_active_slots_avg_occupancy_seconds_has_minimum(
    session: AsyncSession,
):
    limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="low_limit",
            limit=10,
            avg_slot_occupancy_seconds=0.1,
        ),
    )
    await session.commit()

    for _ in range(10):
        await bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=[limit.id],
            slots=1,
            occupancy_seconds=0.001,
        )

        refreshed = await read_concurrency_limit(session, concurrency_limit_id=limit.id)
        assert refreshed

        # `avg_slot_occupancy_seconds` should never be less than
        # MINIMUM_OCCUPANCY_SECONDS_PER_SLOT
        assert (
            refreshed.avg_slot_occupancy_seconds == MINIMUM_OCCUPANCY_SECONDS_PER_SLOT
        )


async def test_bulk_update_denied_slots(
    session: AsyncSession,
    locked_concurrency_limit: ConcurrencyLimitV2,
):
    await bulk_update_denied_slots(
        session=session, concurrency_limit_ids=[locked_concurrency_limit.id], slots=10
    )

    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=locked_concurrency_limit.id
    )
    assert refreshed
    assert refreshed.denied_slots == 10


async def test_denied_slots_decay_uses_clamped_value_for_tag_limits(
    session: AsyncSession,
    db: PrefectDBInterface,
):
    """Verify tag limits decay at clamped rate (30s in OSS)."""
    # Create limit with long avg_slot_occupancy_seconds
    limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="tag:test-long-occupancy",
            limit=10,
            avg_slot_occupancy_seconds=120.0,  # 2 minutes
        ),
    )
    await session.commit()

    # Add 10 denied slots
    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[limit.id],
        slots=10,
    )
    await session.commit()

    # Backdate updated timestamp by 30.5 seconds
    backdated_time = datetime.now(timezone.utc) - timedelta(seconds=30.5)
    await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(db.ConcurrencyLimitV2.id == limit.id)
        .values(updated=backdated_time)
    )
    await session.commit()

    # Trigger recalculation while preserving backdated timestamp
    await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(db.ConcurrencyLimitV2.id == limit.id)
        .values(
            denied_slots=denied_slots_after_decay(db) + 0,
            updated=backdated_time,  # Preserve timestamp
        )
    )
    await session.commit()

    # Verify: With 30s clamp, decay_rate = 1/30 = 0.0333 slots/s
    # 30.5s * 0.0333 = 1.02 slots decayed
    # Expected: 10 - floor(1.02) = 9 denied_slots
    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=limit.id
    )
    assert refreshed
    assert refreshed.denied_slots == 9


async def test_denied_slots_decay_uses_clamped_value_for_non_tag_limits(
    session: AsyncSession,
    db: PrefectDBInterface,
):
    """Verify non-tag limits decay at clamped rate (30s in OSS)."""
    limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="global:test-long-occupancy",
            limit=10,
            avg_slot_occupancy_seconds=120.0,
        ),
    )
    await session.commit()

    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[limit.id],
        slots=30,
    )
    await session.commit()

    backdated_time = datetime.now(timezone.utc) - timedelta(seconds=30.5)
    await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(db.ConcurrencyLimitV2.id == limit.id)
        .values(updated=backdated_time)
    )
    await session.commit()

    await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(db.ConcurrencyLimitV2.id == limit.id)
        .values(
            denied_slots=denied_slots_after_decay(db) + 0,
            updated=backdated_time,
        )
    )
    await session.commit()

    # Verify: With 30s clamp, decay_rate = 1/30 = 0.0333 slots/s
    # 30.5s * 0.0333 = 1.02 slots decayed
    # Expected: 30 - 1 = 29 denied_slots
    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=limit.id
    )
    assert refreshed
    assert refreshed.denied_slots == 29


async def test_denied_slots_decay_not_clamped_for_rate_limits(
    session: AsyncSession,
    db: PrefectDBInterface,
):
    """Verify rate limits use slot_decay_per_second directly (no clamping)."""
    limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="rate:test-explicit-decay",
            limit=10,
            slot_decay_per_second=2.0,  # 2 slots per second
            avg_slot_occupancy_seconds=120.0,  # Should be ignored
        ),
    )
    await session.commit()

    await bulk_update_denied_slots(
        session=session,
        concurrency_limit_ids=[limit.id],
        slots=20,
    )
    await session.commit()

    backdated_time = datetime.now(timezone.utc) - timedelta(seconds=5.0)
    await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(db.ConcurrencyLimitV2.id == limit.id)
        .values(updated=backdated_time)
    )
    await session.commit()

    await session.execute(
        sa.update(db.ConcurrencyLimitV2)
        .where(db.ConcurrencyLimitV2.id == limit.id)
        .values(
            denied_slots=denied_slots_after_decay(db) + 0,
            updated=backdated_time,
        )
    )
    await session.commit()

    # Verify: 20 - floor(5s * 2.0 slots/s) = 10 denied_slots
    refreshed = await read_concurrency_limit(
        session=session, concurrency_limit_id=limit.id
    )
    assert refreshed
    assert refreshed.denied_slots == 10
