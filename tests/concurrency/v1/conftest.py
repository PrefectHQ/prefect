import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.server.models.concurrency_limits import create_concurrency_limit
from prefect.server.schemas.core import ConcurrencyLimit


@pytest.fixture
async def v1_concurrency_limit(session: AsyncSession) -> ConcurrencyLimit:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimit(tag="test", concurrency_limit=1),
    )

    await session.commit()

    return ConcurrencyLimit.model_validate(concurrency_limit, from_attributes=True)


@pytest.fixture
async def other_v1_concurrency_limit(session: AsyncSession) -> ConcurrencyLimit:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimit(tag="other", concurrency_limit=1),
    )

    await session.commit()

    return ConcurrencyLimit.model_validate(concurrency_limit, from_attributes=True)
