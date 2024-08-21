from unittest import mock

import pytest
from httpx import HTTPStatusError, Request, Response
from starlette import status

from prefect import flow, task
from prefect.concurrency.v1.asyncio import (
    _acquire_concurrency_slots,
    _release_concurrency_slots,
)
from prefect.concurrency.v1.sync import concurrency
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.server.schemas.core import ConcurrencyLimit


def test_concurrency_orchestrates_api(concurrency_limit: ConcurrencyLimit):
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

            acquire_spy.assert_called_once_with(
                ["test"], 1, timeout_seconds=None, create_if_missing=True, holder=None
            )

            names, occupy, occupy_seconds, holder = release_spy.call_args[0]
            assert names == ["test"]
            assert occupy == 1
            assert occupy_seconds > 0
            assert holder is None

    assert executed


def test_concurrency_emits_events(
    concurrency_limit: ConcurrencyLimit,
    other_concurrency_limit: ConcurrencyLimit,
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

        assert len(event.related) == 1
        assert dict(event.related[0]) == {
            "prefect.resource.id": (
                f"prefect.concurrency-limit.{other_concurrency_limit.id}"
            ),
            "prefect.resource.role": "concurrency-limit",
        }

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

        assert len(event.related) == 1
        assert dict(event.related[0]) == {
            "prefect.resource.id": f"prefect.concurrency-limit.{concurrency_limit.id}",
            "prefect.resource.role": "concurrency-limit",
        }


def test_concurrency_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimit,
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
    concurrency_limit: ConcurrencyLimit,
):
    executed = False

    def resource_heavy():
        nonlocal executed
        with concurrency("test", occupy=1):
            executed = True

    assert not executed

    resource_heavy()

    assert executed


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
        "prefect.client.orchestration.PrefectClient.increment_concurrency_slots",
        mocked_increment_concurrency_slots,
    )


@pytest.mark.usefixtures("concurrency_limit", "mock_increment_concurrency_slots")
def test_concurrency_respects_timeout():
    with pytest.raises(TimeoutError, match=".*timed out after 0.01 second(s)*."):
        with concurrency("test", occupy=1, timeout_seconds=0.01):
            print("should not be executed")


@pytest.mark.parametrize("names", [[], None])
def test_concurrency_without_limit_names_sync(names):
    executed = False

    def resource_heavy():
        nonlocal executed
        with concurrency(names=names, occupy=1):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.sync._acquire_concurrency_slots",
        wraps=lambda *args, **kwargs: None,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.sync._release_concurrency_slots",
            wraps=lambda *args, **kwargs: None,
        ) as release_spy:
            resource_heavy()

            acquire_spy.assert_not_called()
            release_spy.assert_not_called()

    assert executed
