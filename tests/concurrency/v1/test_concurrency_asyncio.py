from unittest import mock
from uuid import UUID

import pytest
from httpx import HTTPStatusError, Request, Response
from starlette import status

from prefect import flow, task
from prefect.concurrency.v1._asyncio import (
    acquire_concurrency_slots,
    release_concurrency_slots,
)
from prefect.concurrency.v1.asyncio import ConcurrencySlotAcquisitionError, concurrency
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.server.schemas.core import ConcurrencyLimit


async def test_concurrency_orchestrates_api(v1_concurrency_limit: ConcurrencyLimit):
    executed = False
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    async def resource_heavy():
        nonlocal executed
        async with concurrency("test", task_run_id):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.v1.asyncio.acquire_concurrency_slots",
        wraps=acquire_concurrency_slots,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.v1.asyncio.release_concurrency_slots",
            wraps=release_concurrency_slots,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_called_once_with(
                ["test"], task_run_id=task_run_id, timeout_seconds=None
            )

            # On release, we calculate how many seconds the slots were occupied
            # for, so here we really just want to make sure that the value
            # passed as `occupy_seconds` is > 0.

            (
                names,
                _task_run_id,
                occupy_seconds,
            ) = release_spy.call_args[0]
            assert names == ["test"]
            assert _task_run_id == task_run_id
            assert occupy_seconds > 0

    assert executed


async def test_concurrency_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimit,
):
    executed = False
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    @task
    async def resource_heavy():
        nonlocal executed
        async with concurrency("test", task_run_id):
            executed = True

    @flow
    async def my_flow():
        await resource_heavy()

    assert not executed

    await my_flow()

    assert executed


async def test_concurrency_emits_events(
    v1_concurrency_limit: ConcurrencyLimit,
    other_v1_concurrency_limit: ConcurrencyLimit,
    asserting_events_worker: EventsWorker,
    mock_should_emit_events,
    reset_worker_events,
):
    executed = False
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    async def resource_heavy():
        nonlocal executed
        async with concurrency(["test", "other"], task_run_id):
            executed = True

    await resource_heavy()
    assert executed

    await asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 4  # 2 acquire, 2 release

    # Check the events for the `test` concurrency_limit.
    for phase in ["acquired", "released"]:
        event = next(
            filter(
                lambda e: e.event == f"prefect.concurrency-limit.v1.{phase}"
                and e.resource.id
                == f"prefect.concurrency-limit.v1.{v1_concurrency_limit.id}",
                asserting_events_worker._client.events,
            )
        )

        assert dict(event.resource) == {
            "prefect.resource.id": f"prefect.concurrency-limit.v1.{v1_concurrency_limit.id}",
            "prefect.resource.name": v1_concurrency_limit.tag,
            "limit": str(v1_concurrency_limit.concurrency_limit),
            "task_run_id": "00000000-0000-0000-0000-000000000000",
        }

        # Since they were used together we expect that the `test` limit events
        # should also include the `other` limit as a related resource.

        assert len(event.related) == 1
        assert dict(event.related[0]) == {
            "prefect.resource.id": (
                f"prefect.concurrency-limit.v1.{other_v1_concurrency_limit.id}"
            ),
            "prefect.resource.role": "concurrency-limit",
        }

    # Check the events for the `other` concurrency_limit.
    for phase in ["acquired", "released"]:
        event = next(
            filter(
                lambda e: e.event == f"prefect.concurrency-limit.v1.{phase}"
                and e.resource.id
                == f"prefect.concurrency-limit.v1.{other_v1_concurrency_limit.id}",
                asserting_events_worker._client.events,
            )
        )

        assert dict(event.resource) == {
            "prefect.resource.id": (
                f"prefect.concurrency-limit.v1.{other_v1_concurrency_limit.id}"
            ),
            "prefect.resource.name": other_v1_concurrency_limit.tag,
            "limit": str(other_v1_concurrency_limit.concurrency_limit),
            "task_run_id": "00000000-0000-0000-0000-000000000000",
        }

        # Since they were used together we expect that the `other` limit events
        # should also include the `test` limit as a related resource.

        assert len(event.related) == 1
        assert dict(event.related[0]) == {
            "prefect.resource.id": f"prefect.concurrency-limit.v1.{v1_concurrency_limit.id}",
            "prefect.resource.role": "concurrency-limit",
        }


@pytest.fixture
def mock_increment_concurrency_slots(monkeypatch):
    async def mocked_increment_concurrency_slots(*args, **kwargs):
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
        "prefect.client.orchestration.PrefectClient.increment_v1_concurrency_slots",
        mocked_increment_concurrency_slots,
    )


@pytest.mark.usefixtures("concurrency_limit", "mock_increment_concurrency_slots")
async def test_concurrency_respects_timeout():
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(TimeoutError, match=".*timed out after 0.01 second(s)*"):
        async with concurrency("test", task_run_id, timeout_seconds=0.01):
            print("should not be executed")


@pytest.fixture
def mock_increment_concurrency_locked_with_no_retry_after(monkeypatch):
    async def mocked_increment_concurrency_slots(*args, **kwargs):
        response = Response(
            status_code=status.HTTP_423_LOCKED,
        )
        raise HTTPStatusError(
            message="Locked",
            request=Request("GET", "http://test.com"),
            response=response,
        )

    monkeypatch.setattr(
        "prefect.client.orchestration.PrefectClient.increment_v1_concurrency_slots",
        mocked_increment_concurrency_slots,
    )


@pytest.mark.usefixtures(
    "concurrency_limit", "mock_increment_concurrency_locked_with_no_retry_after"
)
async def test_concurrency_raises_when_locked_with_no_retry_after():
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ConcurrencySlotAcquisitionError):
        async with concurrency("test", task_run_id):
            print("should not be executed")


@pytest.fixture
def mock_increment_concurrency_locked_with_details_and_no_retry_after(
    monkeypatch,
):
    async def mocked_increment_concurrency_slots(*args, **kwargs):
        response = Response(
            status_code=status.HTTP_423_LOCKED,
            json={"details": "It's broken"},
        )
        raise HTTPStatusError(
            message="Locked",
            request=Request("GET", "http://test.com"),
            response=response,
        )

    monkeypatch.setattr(
        "prefect.client.orchestration.PrefectClient.increment_v1_concurrency_slots",
        mocked_increment_concurrency_slots,
    )


@pytest.mark.usefixtures(
    "concurrency_limit",
    "mock_increment_concurrency_locked_with_details_and_no_retry_after",
)
async def test_concurrency_raises_when_locked_with_details_and_no_retry_after():
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    with pytest.raises(ConcurrencySlotAcquisitionError):
        async with concurrency("test", task_run_id):
            print("should not be executed")


@pytest.mark.parametrize("names", [[], None])
async def test_concurrency_without_limit_names(names):
    executed = False
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    async def resource_heavy():
        nonlocal executed
        async with concurrency(names, task_run_id):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.v1._asyncio.acquire_concurrency_slots",
        wraps=lambda *args, **kwargs: None,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.v1._asyncio.release_concurrency_slots",
            wraps=lambda *args, **kwargs: None,
        ) as release_spy:
            await resource_heavy()

            acquire_spy.assert_not_called()
            release_spy.assert_not_called()

    assert executed
