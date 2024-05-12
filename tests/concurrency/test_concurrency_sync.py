import asyncio
from unittest import mock

import pytest

from prefect import flow, task
from prefect.concurrency.asyncio import (
    _acquire_concurrency_slots,
    _release_concurrency_slots,
)
from prefect.concurrency.sync import concurrency, rate_limit
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.server.schemas.core import ConcurrencyLimitV2


def test_concurrency_orchestrates_api(concurrency_limit: ConcurrencyLimitV2):
    executed = False

    def resource_heavy():
        nonlocal executed
        with concurrency("test", occupy=1):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.sync._acquire_concurrency_slots",
        wraps=_acquire_concurrency_slots,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.sync._release_concurrency_slots",
            wraps=_release_concurrency_slots,
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
    mock_should_emit_events,
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


@pytest.fixture
def mock_acquire_concurrency_slots(monkeypatch):
    async def blocks_forever(*args, **kwargs):
        while True:
            await asyncio.sleep(1)

    monkeypatch.setattr(
        "prefect.concurrency.sync._acquire_concurrency_slots",
        blocks_forever,
    )


@pytest.mark.usefixtures("concurrency_limit", "mock_acquire_concurrency_slots")
def test_concurrency_respects_timeout():
    with pytest.raises(TimeoutError, match=".*timed out after 0.01 second(s)*."):
        with concurrency("test", occupy=1, timeout_seconds=0.01):
            print("should not be executed")


def test_rate_limit_orchestrates_api(concurrency_limit_with_decay: ConcurrencyLimitV2):
    executed = False

    def resource_heavy():
        nonlocal executed
        rate_limit("test", 1)
        executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.sync._acquire_concurrency_slots",
        wraps=_acquire_concurrency_slots,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.sync._release_concurrency_slots",
            wraps=_release_concurrency_slots,
        ) as release_spy:
            resource_heavy()

            acquire_spy.assert_called_once_with(["test"], 1, mode="rate_limit")

            # When used as a rate limit concurrency slots are not explicitly
            # released.
            release_spy.assert_not_called()

    assert executed


def test_rate_limit_can_be_used_within_a_flow(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
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


def test_rate_limit_mixed_sync_async(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
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
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    other_concurrency_limit_with_decay: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    mock_should_emit_events,
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
