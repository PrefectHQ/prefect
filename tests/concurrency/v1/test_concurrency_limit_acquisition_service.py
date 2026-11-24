import asyncio
from typing import Any
from unittest import mock
from uuid import UUID

import pytest
from httpx import HTTPStatusError, Request, Response

from prefect.client.orchestration import get_client
from prefect.concurrency.v1.services import (
    ConcurrencySlotAcquisitionService,
    ConcurrencySlotAcquisitionServiceError,
)

pytestmark = pytest.mark.clear_db


@pytest.fixture
async def mocked_client(test_database_connection_url):
    async with get_client() as client:
        with mock.patch.object(client, "increment_v1_concurrency_slots", autospec=True):

            class ClientWrapper:
                def __init__(self, client):
                    self.client = client

                async def __aenter__(self):
                    return self.client

                async def __aexit__(self, *args):
                    pass

            wrapped_client = ClientWrapper(client)
            with mock.patch(
                "prefect.concurrency.v1.services.get_client", lambda: wrapped_client
            ):
                yield wrapped_client


async def test_returns_successful_response(mocked_client):
    response = Response(200)
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")

    mocked_method = mocked_client.client.increment_v1_concurrency_slots
    mocked_method.return_value = response

    expected_names = sorted(["api", "database"])

    service = ConcurrencySlotAcquisitionService.instance(frozenset(expected_names))
    future = service.send((task_run_id, None))
    await service.drain()
    returned_response = await asyncio.wrap_future(future)
    assert returned_response == response

    mocked_method.assert_called_once_with(
        task_run_id=task_run_id,
        names=expected_names,
    )


async def test_retries_failed_call_respects_retry_after_header(mocked_client):
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    responses = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("get", "/"),
            response=Response(423, headers={"Retry-After": "2"}),
        ),
        Response(200),
    ]

    mocked_client.client.increment_v1_concurrency_slots.side_effect = responses

    limit_names = sorted(["api", "database"])
    service = ConcurrencySlotAcquisitionService.instance(frozenset(limit_names))

    # Patch `asyncio.sleep` only as seen by the service module. Patching it
    # globally also records sleeps from unrelated background tasks.
    sleep = mock.AsyncMock()
    with mock.patch(
        "prefect.concurrency.v1.services.asyncio", wraps=asyncio, sleep=sleep
    ):
        future = service.send((task_run_id, None))
        await service.drain()
        returned_response = await asyncio.wrap_future(future)

        assert returned_response == responses[1]

        sleep.assert_called_once_with(
            float(responses[0].response.headers["Retry-After"])
        )
        assert mocked_client.client.increment_v1_concurrency_slots.call_count == 2


@pytest.mark.parametrize(
    ("headers", "expected_delay"),
    [
        ({"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}, 0.0),
        ({"Retry-After": "not-a-number"}, 1.0),
    ],
)
async def test_retries_failed_call_with_unusable_retry_after_header(
    mocked_client: Any, headers: dict[str, str], expected_delay: float
) -> None:
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    responses = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("get", "/"),
            response=Response(423, headers=headers),
        ),
        Response(200),
    ]
    mocked_client.client.increment_v1_concurrency_slots.side_effect = responses

    service = ConcurrencySlotAcquisitionService.instance(frozenset(["api", "database"]))

    sleep = mock.AsyncMock()
    with mock.patch(
        "prefect.concurrency.v1.services.asyncio", wraps=asyncio, sleep=sleep
    ):
        future = service.send((task_run_id, None))
        await service.drain()
        returned_response = await asyncio.wrap_future(future)

        assert returned_response == responses[1]
        sleep.assert_called_once_with(expected_delay)
        assert mocked_client.client.increment_v1_concurrency_slots.call_count == 2


async def test_missing_retry_after_header_still_aborts(mocked_client: Any) -> None:
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    response = HTTPStatusError(
        "Limit is locked",
        request=Request("get", "/"),
        response=Response(423),
    )
    mocked_client.client.increment_v1_concurrency_slots.side_effect = response

    service = ConcurrencySlotAcquisitionService.instance(frozenset(["api", "database"]))

    future = service.send((task_run_id, None))
    await service.drain()
    with pytest.raises(ConcurrencySlotAcquisitionServiceError):
        await asyncio.wrap_future(future)


async def test_failed_call_status_code_not_retryable_returns_exception(mocked_client):
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    response = HTTPStatusError(
        "Too many requests",
        request=Request("get", "/"),
        response=Response(500, headers={"Retry-After": "2"}),
    )

    mocked_client.client.increment_v1_concurrency_slots.return_value = response

    limit_names = sorted(["api", "database"])
    service = ConcurrencySlotAcquisitionService.instance(frozenset(limit_names))

    future = service.send((task_run_id, None))
    await service.drain()
    exception = await asyncio.wrap_future(future)

    assert isinstance(exception, HTTPStatusError)
    assert exception == response


async def test_basic_exception_returns_exception(mocked_client):
    task_run_id = UUID("00000000-0000-0000-0000-000000000000")
    exc = Exception("Something went wrong")
    mocked_client.client.increment_v1_concurrency_slots.side_effect = exc

    limit_names = sorted(["api", "database"])
    service = ConcurrencySlotAcquisitionService.instance(frozenset(limit_names))

    future = service.send((task_run_id, None))
    await service.drain()
    with pytest.raises(Exception) as info:
        await asyncio.wrap_future(future)

    assert info.value == exc
