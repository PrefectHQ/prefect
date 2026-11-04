import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.models.concurrency_limits_v2 import create_concurrency_limit
from prefect.server.schemas.core import ConcurrencyLimitV2


@pytest.fixture
async def concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="test", limit=1),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def slow_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    # Slots on this limit have been held for a minute on average, so the server
    # tells a refused caller to retry after its maximum wait of 30 seconds
    # (between about 22 and 39 seconds once jittered).
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test", limit=1, avg_slot_occupancy_seconds=60
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def other_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="other", limit=1),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def concurrency_limit_with_decay(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test", limit=1, slot_decay_per_second=0.1
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def other_concurrency_limit_with_decay(
    session: AsyncSession,
) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="other", limit=1, slot_decay_per_second=0.1
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.model_validate(concurrency_limit, from_attributes=True)
