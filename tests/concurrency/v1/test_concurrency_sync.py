from unittest import mock
from uuid import UUID

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
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    def resource_heavy():
        nonlocal executed
        with concurrency("test", task_run_id):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.v1.sync._acquire_concurrency_slots",
        wraps=_acquire_concurrency_slots,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.v1.sync._release_concurrency_slots",
            wraps=_release_concurrency_slots,
        ) as release_spy:
            resource_heavy()

            acquire_spy.assert_called_once_with(
                ["test"], timeout_seconds=None, task_run_id=task_run_id, _sync=True
            )

            names, _task_run_id, occupy_seconds = release_spy.call_args[0]
            assert names == ["test"]
            assert _task_run_id == task_run_id
            assert occupy_seconds > 0

    assert executed


def test_concurrency_emits_events(
    v1_concurrency_limit: ConcurrencyLimit,
    other_v1_concurrency_limit: ConcurrencyLimit,
    asserting_events_worker: EventsWorker,
    mock_should_emit_events,
    reset_worker_events,
):
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    def resource_heavy():
        with concurrency(["test", "other"], task_run_id):
            pass

    resource_heavy()

    asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 4  # 2 acquire, 2 release

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
            "task_run_id": str(task_run_id),
            "limit": str(v1_concurrency_limit.concurrency_limit),
        }

        assert len(event.related) == 1
        assert dict(event.related[0]) == {
            "prefect.resource.id": (
                f"prefect.concurrency-limit.v1.{other_v1_concurrency_limit.id}"
            ),
            "prefect.resource.role": "concurrency-limit",
        }

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
            "task_run_id": str(task_run_id),
            "limit": str(other_v1_concurrency_limit.concurrency_limit),
        }

        assert len(event.related) == 1
        assert dict(event.related[0]) == {
            "prefect.resource.id": f"prefect.concurrency-limit.v1.{v1_concurrency_limit.id}",
            "prefect.resource.role": "concurrency-limit",
        }


def test_concurrency_can_be_used_within_a_flow(
    concurrency_limit: ConcurrencyLimit,
):
    executed = False
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    @task
    def resource_heavy():
        nonlocal executed
        with concurrency("test", task_run_id):
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
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    def resource_heavy():
        nonlocal executed
        with concurrency("test", task_run_id):
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
        "prefect.client.orchestration.PrefectClient.increment_v1_concurrency_slots",
        mocked_increment_concurrency_slots,
    )


@pytest.mark.usefixtures("concurrency_limit", "mock_increment_concurrency_slots")
def test_concurrency_respects_timeout():
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    with pytest.raises(TimeoutError, match=".*timed out after 0.01 second(s)*."):
        with concurrency("test", task_run_id=task_run_id, timeout_seconds=0.01):
            print("should not be executed")


@pytest.mark.parametrize("names", [[], None])
def test_concurrency_without_limit_names_sync(names):
    executed = False
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    def resource_heavy():
        nonlocal executed
        with concurrency(names=names, task_run_id=task_run_id):
            executed = True

    assert not executed

    with mock.patch(
        "prefect.concurrency.v1.sync._acquire_concurrency_slots",
        wraps=lambda *args, **kwargs: None,
    ) as acquire_spy:
        with mock.patch(
            "prefect.concurrency.v1.sync._release_concurrency_slots",
            wraps=lambda *args, **kwargs: None,
        ) as release_spy:
            resource_heavy()

            acquire_spy.assert_not_called()
            release_spy.assert_not_called()

    assert executed
