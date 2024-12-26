import asyncio
from unittest import mock
from uuid import UUID

import pytest
from httpx import HTTPStatusError, Request, Response

from prefect.client.orchestration import get_client
from prefect.concurrency.v1.services import ConcurrencySlotAcquisitionService


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

    with mock.patch("asyncio.sleep") as sleep:
        future = service.send((task_run_id, None))
        service.drain()
        returned_response = await asyncio.wrap_future(future)

        assert returned_response == responses[1]

        sleep.assert_called_once_with(
            float(responses[0].response.headers["Retry-After"])
        )
        assert mocked_client.client.increment_v1_concurrency_slots.call_count == 2


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
