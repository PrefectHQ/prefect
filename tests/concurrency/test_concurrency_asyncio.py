from unittest import mock

from prefect import flow, task
from prefect.concurrency.asyncio import (
    _acquire_concurrency_slots,
    _release_concurrency_slots,
    concurrency,
    rate_limit,
)
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.server.schemas.core import ConcurrencyLimitV2


async def test_concurrency_orchestrates_api(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    async def resource_heavy():
        nonlocal executed
        async with concurrency("test", occupy=1):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.asyncio._acquire_concurrency_slots",
        wraps=_acquire_concurrency_slots,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.asyncio._release_concurrency_slots",
            wraps=_release_concurrency_slots,
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


async def test_concurrency_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        async with concurrency("test", occupy=1):
            executed = True

    @flow
    async def my_flow():
        await resource_heavy()

    assert not executed

    await my_flow()

    assert executed


def test_concurrency_mixed_sync_async(
    concurrency_limit: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        async with concurrency("test", occupy=1):
            executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


async def test_concurrency_emits_events(
    concurrency_limit: ConcurrencyLimitV2,
    other_concurrency_limit: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    reset_worker_events,
):
    executed = False

    async def resource_heavy():
        nonlocal executed
        async with concurrency(["test", "other"], occupy=1):
            executed = True

    await resource_heavy()

    await asserting_events_worker.drain()
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


async def test_rate_limit_orchestrates_api(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
):
    executed = False

    async def resource_heavy():
        nonlocal executed
        await rate_limit("test", 1)
        executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.asyncio._acquire_concurrency_slots",
        wraps=_acquire_concurrency_slots,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.asyncio._release_concurrency_slots",
            wraps=_release_concurrency_slots,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_called_once_with(["test"], 1, mode="rate_limit")

            # When used as a rate limit concurrency slots are not explicitly
            # released.
            release_spy.assert_not_called()

    assert executed


async def test_rate_limit_can_be_used_within_a_flow(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        await rate_limit("test", occupy=1)
        executed = True

    @flow
    async def my_flow():
        await resource_heavy()

    assert not executed

    await my_flow()

    assert executed


def test_rate_limit_mixed_sync_async(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
):
    executed = False

    @task
    async def resource_heavy():
        nonlocal executed
        await rate_limit("test", occupy=1)
        executed = True

    @flow
    def my_flow():
        resource_heavy()

    assert not executed

    my_flow()

    assert executed


async def test_rate_limit_emits_events(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    other_concurrency_limit_with_decay: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    reset_worker_events,
):
    async def resource_heavy():
        await rate_limit(["test", "other"], occupy=1)

    await resource_heavy()

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 2

    # Check the event for the `test` concurrency_limit.
    event = next(
        filter(
            lambda e: e.resource.id
            == f"prefect.concurrency-limit.{concurrency_limit_with_decay.id}",
            asserting_events_worker._client.events,
        )
    )

    assert event.event == "prefect.concurrency-limit.acquired"
    assert dict(event.resource) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{concurrency_limit_with_decay.id}"
        ),
        "prefect.resource.name": concurrency_limit_with_decay.name,
        "slots-acquired": "1",
        "limit": str(concurrency_limit_with_decay.limit),
    }

    # Since they were used together we expect that the `test` limit events
    # should also include the `other` limit as a related resource.

    assert len(event.related) == 1
    assert dict(event.related[0]) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{other_concurrency_limit_with_decay.id}"
        ),
        "prefect.resource.role": "concurrency-limit",
    }

    # Check the event for the `other` concurrency_limit.
    event = next(
        filter(
            lambda e: e.resource.id
            == f"prefect.concurrency-limit.{other_concurrency_limit_with_decay.id}",
            asserting_events_worker._client.events,
        )
    )

    assert event.event == "prefect.concurrency-limit.acquired"
    assert dict(event.resource) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{other_concurrency_limit_with_decay.id}"
        ),
        "prefect.resource.name": other_concurrency_limit_with_decay.name,
        "slots-acquired": "1",
        "limit": str(other_concurrency_limit_with_decay.limit),
    }

    # Since they were used together we expect that the `other` limit events
    # should also include the `test` limit as a related resource.

    assert len(event.related) == 1
    assert dict(event.related[0]) == {
        "prefect.resource.id": (
            f"prefect.concurrency-limit.{concurrency_limit_with_decay.id}"
        ),
        "prefect.resource.role": "concurrency-limit",
    }
