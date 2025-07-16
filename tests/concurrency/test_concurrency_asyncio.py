from typing import Any
from unittest import mock
from uuid import UUID

import pytest
from httpx import HTTPStatusError, Request, Response
from starlette import status

from prefect import flow, task
from prefect.concurrency._asyncio import (
    aacquire_concurrency_slots,
    aacquire_concurrency_slots_with_lease,
    arelease_concurrency_slots_with_lease,
)
from prefect.concurrency.asyncio import (
    ConcurrencySlotAcquisitionError,
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
        "prefect.concurrency.asyncio.aacquire_concurrency_slots_with_lease",
        wraps=aacquire_concurrency_slots_with_lease,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.asyncio.arelease_concurrency_slots_with_lease",
            wraps=arelease_concurrency_slots_with_lease,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_called_once_with(
                names=["test"],
                slots=1,
                timeout_seconds=None,
                max_retries=None,
                lease_duration=300,
                strict=False,
            )

            # On release we calculate how many seconds the slots were occupied
            # for, so here we really just want to make sure that the value
            # passed as `occupy_seconds` is > 0.

            lease_id = release_spy.call_args[1]["lease_id"]
            occupancy_seconds = release_spy.call_args[1]["occupancy_seconds"]

            assert isinstance(lease_id, UUID)
            assert occupancy_seconds > 0.0

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


async def test_concurrency_can_be_used_within_a_flow_strictly():
    @task
    async def resource_heavy():
        async with concurrency("santa-clause", occupy=1, strict=True):
            return

    @flow
    async def my_flow():
        await resource_heavy()

    state = await my_flow(return_state=True)
    assert state.is_failed()
    with pytest.raises(ConcurrencySlotAcquisitionError):
        await state.result()  # type: ignore[reportGeneralTypeIssues]


async def test_concurrency_emits_events(
    concurrency_limit: ConcurrencyLimitV2,
    other_concurrency_limit: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    mock_should_emit_events,
    reset_worker_events,
):
    executed = False

    async def resource_heavy():
        nonlocal executed
        async with concurrency(["test", "other"], occupy=1):
            executed = True

    await resource_heavy()

    await asserting_events_worker.drain()  # type: ignore[reportGeneralTypeIssues]
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


@pytest.fixture
def mock_increment_concurrency_slots(monkeypatch: pytest.MonkeyPatch):
    async def mocked_increment_concurrency_slots(*args: Any, **kwargs: Any):
        response = Response(
            status_code=status.HTTP_423_LOCKED,
            headers={"Retry-After": "0.01"},
        )
        raise HTTPStatusError(
            message="Locked",
            request=Request("GET", "http://test.com"),
            response=response,
        )

    monkeypatch.setattr(
        "prefect.client.orchestration.PrefectClient.increment_concurrency_slots_with_lease",
        mocked_increment_concurrency_slots,
    )


@pytest.mark.usefixtures("concurrency_limit", "mock_increment_concurrency_slots")
async def test_concurrency_respects_timeout():
    with pytest.raises(TimeoutError, match=".*timed out after 0.01 second(s)*"):
        async with concurrency("test", occupy=1, timeout_seconds=0.01):
            print("should not be executed")


@pytest.mark.usefixtures("mock_increment_concurrency_slots")
async def test_concurrency_respects_max_retries():
    with pytest.raises(ConcurrencySlotAcquisitionError):
        async with concurrency("test", occupy=1, max_retries=0, timeout_seconds=5):
            print("should not be executed")


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
        "prefect.concurrency.asyncio.aacquire_concurrency_slots",
        wraps=aacquire_concurrency_slots,
    ) as acquire_spy:
        await resource_heavy()

        acquire_spy.assert_called_once_with(
            names=["test"],
            slots=1,
            mode="rate_limit",
            timeout_seconds=None,
            strict=False,
        )

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


async def test_rate_limit_can_be_used_within_a_flow_with_strict():
    @task
    async def resource_heavy():
        await rate_limit("easter-bunny", occupy=1, strict=True)
        return

    @flow
    async def my_flow():
        await resource_heavy()

    state = await my_flow(return_state=True)
    assert state.is_failed()
    with pytest.raises(ConcurrencySlotAcquisitionError):
        await state.result()  # type: ignore[reportGeneralTypeIssues]


async def test_rate_limit_emits_events(
    concurrency_limit_with_decay: ConcurrencyLimitV2,
    other_concurrency_limit_with_decay: ConcurrencyLimitV2,
    asserting_events_worker: EventsWorker,
    mock_should_emit_events,
    reset_worker_events,
):
    async def resource_heavy():
        await rate_limit(["test", "other"], occupy=1)

    await resource_heavy()

    await asserting_events_worker.drain()  # type: ignore[reportGeneralTypeIssues]
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


@pytest.mark.parametrize("names", [[], None])
async def test_rate_limit_without_limit_names(names):
    executed = False

    async def resource_heavy():
        nonlocal executed
        await rate_limit(names=names, occupy=1)
        executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.sync._acquire_concurrency_slots",
        wraps=lambda *args, **kwargs: None,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.sync.arelease_concurrency_slots",
            wraps=lambda *args, **kwargs: None,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_not_called()
            release_spy.assert_not_called()

    assert executed


@pytest.mark.parametrize("names", [[], None])
async def test_concurrency_without_limit_names(names):
    executed = False

    async def resource_heavy():
        nonlocal executed
        async with concurrency(names=names, occupy=1):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.sync._acquire_concurrency_slots",
        wraps=lambda *args, **kwargs: None,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.sync.arelease_concurrency_slots",
            wraps=lambda *args, **kwargs: None,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_not_called()
            release_spy.assert_not_called()

    assert executed
