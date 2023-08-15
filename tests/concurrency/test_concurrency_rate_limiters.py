import pytest
from unittest import mock
from sqlalchemy.ext.asyncio import AsyncSession

from prefect import flow, task
from prefect.concurrency import (
    arate_limit,
    acquire_concurrency_slots,
    rate_limit,
    release_concurrency_slots,
)
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.server.schemas.core import ConcurrencyLimitV2
from prefect.server.models.concurrency_limits_v2 import create_concurrency_limit


@pytest.fixture
async def concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="test", limit=1, slot_decay_per_second=0.1
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.from_orm(concurrency_limit)


@pytest.fixture
async def other_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(
            name="other", limit=1, slot_decay_per_second=0.1
        ),
    )

    await session.commit()

    return ConcurrencyLimitV2.from_orm(concurrency_limit)


async def test_arate_limit_orchestrates_api(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    async def resource_heavy():
        nonlocal executed
        await arate_limit("test", 1)
        executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.acquire_concurrency_slots", wraps=acquire_concurrency_slots
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.release_concurrency_slots",
            wraps=release_concurrency_slots,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_called_once_with(["test"], 1, mode="rate_limit")

            # When used as a rate limit concurrency slots are not explicitly
            # released.
            release_spy.assert_not_called()

    assert executed


async def test_arate_limit_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        await arate_limit("test", occupy=1)
        executed = True

    @flow
    async def my_flow():
        await resource_heavy()

    assert not executed

    await my_flow()

    assert executed


def test_arate_limit_mixed_sync_async(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        await arate_limit("test", occupy=1)
        executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


async def test_arate_limit_emits_events(
    concurrency_limit: ConcurrencyLimitV2,
    other_concurrency_limit: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    reset_worker_events,
):
    async def resource_heavy():
        await arate_limit(["test", "other"], occupy=1)

    await resource_heavy()

    asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 2

    # Check the event for the `test` concurrency_limit.
    event = next(
        filter(
            lambda e: e.resource.id
            == f"prefect.concurrency-limit.{concurrency_limit.id}",
            asserting_events_worker._client.events,
        )
    )

    assert event.event == "prefect.concurrency-limit.acquired"
    assert dict(event.resource) == {
        "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
        "prefect.resource.name": concurrency_limit.name,
        "slots-acquired": "1",
        "limit": str(concurrency_limit.limit),
    }

    # Since they were used together we expect that the `test` limit events
    # should also include the `other` limit as a related resource.

    assert len(event.related) == 1
    assert dict(event.related[0]) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{other_concurrency_limit.id}"
        ),
        "prefect.resource.role": "concurrency-limit",
    }

    # Check the event for the `other` concurrency_limit.
    event = next(
        filter(
            lambda e: e.resource.id
            == f"prefect.concurrency-limit.{other_concurrency_limit.id}",
            asserting_events_worker._client.events,
        )
    )

    assert event.event == "prefect.concurrency-limit.acquired"
    assert dict(event.resource) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{other_concurrency_limit.id}"
        ),
        "prefect.resource.name": other_concurrency_limit.name,
        "slots-acquired": "1",
        "limit": str(other_concurrency_limit.limit),
    }

    # Since they were used together we expect that the `other` limit events
    # should also include the `test` limit as a related resource.

    assert len(event.related) == 1
    assert dict(event.related[0]) == {
        "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
        "prefect.resource.role": "concurrency-limit",
    }


def test_rate_limit_orchestrates_api(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    def resource_heavy():
        nonlocal executed
        rate_limit("test", 1)
        executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.acquire_concurrency_slots", wraps=acquire_concurrency_slots
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.release_concurrency_slots",
            wraps=release_concurrency_slots,
        ) as release_spy:
            resource_heavy()

            acquire_spy.assert_called_once_with(["test"], 1, mode="rate_limit")

            # When used as a rate limit concurrency slots are not explicitly
            # released.
            release_spy.assert_not_called()

    assert executed


def test_rate_limit_can_be_used_within_a_flow(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    @task
    def resource_heavy():
        nonlocal executed
        rate_limit("test", occupy=1)
        executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


def test_rate_limit_mixed_sync_async(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    def resource_heavy():
        nonlocal executed
        rate_limit("test", occupy=1)
        executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


def test_rate_limit_emits_events(
    concurrency_limit: ConcurrencyLimitV2,
    other_concurrency_limit: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    reset_worker_events,
):
    def resource_heavy():
        rate_limit(["test", "other"], occupy=1)

    resource_heavy()

    asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 2

    # Check the event for the `test` concurrency_limit.
    event = next(
        filter(
            lambda e: e.resource.id
            == f"prefect.concurrency-limit.{concurrency_limit.id}",
            asserting_events_worker._client.events,
        )
    )

    assert event.event == "prefect.concurrency-limit.acquired"
    assert dict(event.resource) == {
        "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
        "prefect.resource.name": concurrency_limit.name,
        "slots-acquired": "1",
        "limit": str(concurrency_limit.limit),
    }

    # Since they were used together we expect that the `test` limit events
    # should also include the `other` limit as a related resource.

    assert len(event.related) == 1
    assert dict(event.related[0]) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{other_concurrency_limit.id}"
        ),
        "prefect.resource.role": "concurrency-limit",
    }

    # Check the event for the `other` concurrency_limit.
    event = next(
        filter(
            lambda e: e.resource.id
            == f"prefect.concurrency-limit.{other_concurrency_limit.id}",
            asserting_events_worker._client.events,
        )
    )

    assert event.event == "prefect.concurrency-limit.acquired"
    assert dict(event.resource) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{other_concurrency_limit.id}"
        ),
        "prefect.resource.name": other_concurrency_limit.name,
        "slots-acquired": "1",
        "limit": str(other_concurrency_limit.limit),
    }

    # Since they were used together we expect that the `other` limit events
    # should also include the `test` limit as a related resource.

    assert len(event.related) == 1
    assert dict(event.related[0]) == {
        "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
        "prefect.resource.role": "concurrency-limit",
    }
