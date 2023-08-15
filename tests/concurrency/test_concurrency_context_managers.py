import pytest
from unittest import mock
from sqlalchemy.ext.asyncio import AsyncSession

from prefect import flow, task
from prefect.concurrency import (
    aconcurrency,
    acquire_concurrency_slots,
    concurrency,
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
        concurrency_limit=ConcurrencyLimitV2(name="test", limit=1),
    )

    await session.commit()

    return ConcurrencyLimitV2.from_orm(concurrency_limit)


@pytest.fixture
async def other_concurrency_limit(session: AsyncSession) -> ConcurrencyLimitV2:
    concurrency_limit = await create_concurrency_limit(
        session=session,
        concurrency_limit=ConcurrencyLimitV2(name="other", limit=1),
    )

    await session.commit()

    return ConcurrencyLimitV2.from_orm(concurrency_limit)


async def test_aconcurrency_orchestrates_api(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    async def resource_heavy():
        nonlocal executed
        async with aconcurrency("test", occupy=1):
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

            acquire_spy.assert_called_once_with(["test"], 1)

            # On release we calculate how many seconds the slots were occupied
            # for, so here we really just want to make sure that the value
            # passed as `occupy_seconds` is > 0.

            names, occupy, occupy_seconds = release_spy.call_args[0]
            assert names == ["test"]
            assert occupy == 1
            assert occupy_seconds > 0

    assert executed


async def test_aconcurrency_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        async with aconcurrency("test", occupy=1):
            executed = True

    @flow
    async def my_flow():
        await resource_heavy()

    assert not executed

    await my_flow()

    assert executed


def test_aconcurrency_mixed_sync_async(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        async with aconcurrency("test", occupy=1):
            executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


async def test_aconcurrency_emits_events(
    concurrency_limit: ConcurrencyLimitV2,
    other_concurrency_limit: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    reset_worker_events,
):
    async def resource_heavy():
        async with aconcurrency(["test", "other"], occupy=1):
            pass

    await resource_heavy()

    asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 4  # 2 acquire, 2 release

    # Check the events for the `test` concurrency_limit.
    for phase in ["acquired", "released"]:
        event = next(
            filter(
                lambda e: e.event == f"prefect.concurrency-limit.{phase}"
                and e.resource.id
                == f"prefect.concurrency-limit.{concurrency_limit.id}",
                asserting_events_worker._client.events,
            )
        )

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

    # Check the events for the `other` concurrency_limit.
    for phase in ["acquired", "released"]:
        event = next(
            filter(
                lambda e: e.event == f"prefect.concurrency-limit.{phase}"
                and e.resource.id
                == f"prefect.concurrency-limit.{other_concurrency_limit.id}",
                asserting_events_worker._client.events,
            )
        )

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


def test_concurrency_orchestrates_api(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    def resource_heavy():
        nonlocal executed
        with concurrency("test", occupy=1):
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

            acquire_spy.assert_called_once_with(["test"], 1)

            # On release we calculate how many seconds the slots were occupied
            # for, so here we really just want to make sure that the value
            # passed as `occupy_seconds` is > 0.

            names, occupy, occupy_seconds = release_spy.call_args[0]
            assert names == ["test"]
            assert occupy == 1
            assert occupy_seconds > 0

    assert executed


def test_concurrency_emits_events(
    concurrency_limit: ConcurrencyLimitV2,
    other_concurrency_limit: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    reset_worker_events,
):
    def resource_heavy():
        with concurrency(["test", "other"], occupy=1):
            pass

    resource_heavy()

    asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 4  # 2 acquire, 2 release

    # Check the events for the `test` concurrency_limit.
    for phase in ["acquired", "released"]:
        event = next(
            filter(
                lambda e: e.event == f"prefect.concurrency-limit.{phase}"
                and e.resource.id
                == f"prefect.concurrency-limit.{concurrency_limit.id}",
                asserting_events_worker._client.events,
            )
        )

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

    # Check the events for the `other` concurrency_limit.
    for phase in ["acquired", "released"]:
        event = next(
            filter(
                lambda e: e.event == f"prefect.concurrency-limit.{phase}"
                and e.resource.id
                == f"prefect.concurrency-limit.{other_concurrency_limit.id}",
                asserting_events_worker._client.events,
            )
        )

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


def test_concurrency_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    def resource_heavy():
        nonlocal executed
        with concurrency("test", occupy=1):
            executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


async def test_concurrency_can_be_used_while_event_loop_is_running(
    concurrency_limit: ConcurrencyLimitV2,
):
    # There are two ways that we'll try to call the async client functions,
    # this is to test the path where there is an event loop, but for some
    # reason the context manager is being used inside of a sync function.

    executed = False

    def resource_heavy():
        nonlocal executed
        with concurrency("test", occupy=1):
            executed = True

    assert not executed

    resource_heavy()

    assert executed
