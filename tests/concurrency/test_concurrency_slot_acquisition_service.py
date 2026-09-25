import asyncio
from unittest import mock

import pytest
from httpx import HTTPStatusError, Request, Response

from prefect.client.orchestration import get_client
from prefect.concurrency.services import (
    ConcurrencySlotAcquisitionService,
    _notify_concurrency_slots_released,
    _SlotReleaseWaiter,
)

pytestmark = pytest.mark.clear_db


@pytest.fixture
async def mocked_client(test_database_connection_url):
    async with get_client() as client:
        with mock.patch.object(client, "increment_concurrency_slots", autospec=True):

            class ClientWrapper:
                def __init__(self, client):
                    self.client = client

                async def __aenter__(self):
                    return self.client

                async def __aexit__(self, *args):
                    pass

            wrapped_client = ClientWrapper(client)
            with mock.patch(
                "prefect.concurrency.services.get_client", lambda: wrapped_client
            ):
                yield wrapped_client


async def test_returns_successful_response(mocked_client):
    response = Response(200)

    mocked_method = mocked_client.client.increment_concurrency_slots
    mocked_method.return_value = response

    expected_names = sorted(["api", "database"])
    expected_slots = 1
    expected_mode = "concurrency"

    service = ConcurrencySlotAcquisitionService.instance(frozenset(expected_names))
    future = service.send((expected_slots, expected_mode, None, None))
    await service.drain()
    returned_response = await asyncio.wrap_future(future)
    assert returned_response == response

    mocked_method.assert_called_once_with(
        names=expected_names,
        slots=expected_slots,
        mode=expected_mode,
    )


async def test_retries_failed_call_respects_retry_after_header(mocked_client):
    responses = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("get", "/"),
            response=Response(423, headers={"Retry-After": "2"}),
        ),
        Response(200),
    ]

    mocked_client.client.increment_concurrency_slots.side_effect = responses

    limit_names = sorted(["api", "database"])
    service = ConcurrencySlotAcquisitionService.instance(frozenset(limit_names))

    with mock.patch.object(_SlotReleaseWaiter, "wait", autospec=True) as wait:
        future = service.send((1, "concurrency", None, None))
        await service.drain()
        returned_response = await asyncio.wrap_future(future)

        assert returned_response == responses[1]

        wait.assert_called_once_with(
            mock.ANY, float(responses[0].response.headers["Retry-After"])
        )
        assert mocked_client.client.increment_concurrency_slots.call_count == 2


async def test_local_release_wakes_waiter_before_retry_after(mocked_client):
    responses = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("get", "/"),
            response=Response(423, headers={"Retry-After": "60"}),
        ),
        Response(200),
    ]
    mocked_client.client.increment_concurrency_slots.side_effect = responses

    service = ConcurrencySlotAcquisitionService.instance(frozenset(["api"]))
    future = service.send((1, "concurrency", None, None))

    while mocked_client.client.increment_concurrency_slots.call_count < 1:
        await asyncio.sleep(0.01)

    _notify_concurrency_slots_released(["api"])

    returned_response = await asyncio.wait_for(asyncio.wrap_future(future), 5)
    assert returned_response == responses[1]
    assert mocked_client.client.increment_concurrency_slots.call_count == 2
    await service.drain()


async def test_release_of_unrelated_limit_does_not_wake_waiter(mocked_client):
    mocked_client.client.increment_concurrency_slots.side_effect = [
        HTTPStatusError(
            "Limit is locked",
            request=Request("get", "/"),
            response=Response(423, headers={"Retry-After": "60"}),
        ),
        Response(200),
    ]

    service = ConcurrencySlotAcquisitionService.instance(frozenset(["api"]))
    with mock.patch.object(
        service, "_notify_slots_released", wraps=service._notify_slots_released
    ) as notify:
        future = service.send((1, "concurrency", None, None))

        while mocked_client.client.increment_concurrency_slots.call_count < 1:
            await asyncio.sleep(0.01)

        _notify_concurrency_slots_released(["database"])
        await asyncio.sleep(0.1)

        notify.assert_not_called()
        assert not future.done()
        assert mocked_client.client.increment_concurrency_slots.call_count == 1

        _notify_concurrency_slots_released(["api"])
        await asyncio.wait_for(asyncio.wrap_future(future), 5)
        notify.assert_called_once()
    await service.drain()


async def test_failed_call_status_code_not_retryable_returns_exception(mocked_client):
    response = HTTPStatusError(
        "Too many requests",
        request=Request("get", "/"),
        response=Response(500, headers={"Retry-After": "2"}),
    )

    mocked_client.client.increment_concurrency_slots.return_value = response

    limit_names = sorted(["api", "database"])
    service = ConcurrencySlotAcquisitionService.instance(frozenset(limit_names))

    future = service.send((1, "concurrency", None, None))
    await service.drain()
    exception = await asyncio.wrap_future(future)

    assert isinstance(exception, HTTPStatusError)
    assert exception == response


async def test_basic_exception_returns_exception(mocked_client):
    exc = Exception("Something went wrong")
    mocked_client.client.increment_concurrency_slots.side_effect = exc

    limit_names = sorted(["api", "database"])
    service = ConcurrencySlotAcquisitionService.instance(frozenset(limit_names))

    future = service.send((1, "concurrency", None, None))
    await service.drain()

    with pytest.raises(Exception) as info:
        await asyncio.wrap_future(future)

    assert info.value == exc
