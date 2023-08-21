from unittest import mock

import pytest
from httpx import HTTPStatusError, Request, Response

from prefect.concurrency.asyncio import wait_for_successful_response
from prefect.settings import PREFECT_CLIENT_RETRY_JITTER_FACTOR
from prefect.testing.utilities import AsyncMock


async def test_calls_fn_and_returns_response():
    response = Response(200)
    expected_args = (1, 2, 3)
    expected_kwargs = {"a": 1, "b": 2, "c": 3}

    requester = AsyncMock(return_value=response)

    result = await wait_for_successful_response(
        requester, *expected_args, **expected_kwargs
    )
    assert result == response

    requester.assert_called_once_with(*expected_args, **expected_kwargs)


async def test_retries_failed_call_exponential_backoff():
    responses = [
        HTTPStatusError(
            "Too many requests", request=Request("get", "/"), response=Response(429)
        ),
        HTTPStatusError(
            "Too many requests", request=Request("get", "/"), response=Response(429)
        ),
        Response(200),
    ]
    expected_args = (1, 2, 3)
    expected_kwargs = {"a": 1, "b": 2, "c": 3}

    requester = AsyncMock()
    requester.side_effect = responses

    with mock.patch(
        "prefect.concurrency.asyncio.clamped_poisson_interval"
    ) as clamped_poisson_interval:
        with mock.patch("prefect.concurrency.asyncio.asyncio.sleep") as sleep:
            clamped_poisson_interval.side_effect = [2, 4]

            result = await wait_for_successful_response(
                requester, *expected_args, **expected_kwargs
            )
            assert result == responses[2]

            # `clamped_poisson_interval` is called during each retry with the
            # number of retries squared as the argument. So we assert that it's
            # called with 2 and 4, respectively. Then above it's mocked out to
            # return 2 and 4, respectively, which are then passed to `sleep`.
            clamped_poisson_interval.assert_has_calls([mock.call(2), mock.call(4)])
            sleep.assert_has_calls([mock.call(2), mock.call(4)])


async def test_retries_failed_call_exponential_backoff_max_seconds():
    responses = [
        HTTPStatusError(
            "Too many requests", request=Request("get", "/"), response=Response(429)
        ),
        HTTPStatusError(
            "Too many requests", request=Request("get", "/"), response=Response(429)
        ),
        Response(200),
    ]

    requester = AsyncMock()
    requester.side_effect = responses

    with mock.patch(
        "prefect.concurrency.asyncio.clamped_poisson_interval"
    ) as clamped_poisson_interval:
        with mock.patch("prefect.concurrency.asyncio.asyncio.sleep"):
            clamped_poisson_interval.side_effect = [2, 4]

            result = await wait_for_successful_response(requester, max_retry_seconds=3)
            assert result == responses[2]

            # `clamped_poisson_interval` is called during each retry with the
            # number of retries squared as the argument, unless it's over
            # `max_retry_seconds`, and then it's just called with
            # `max_retry_seconds`.
            clamped_poisson_interval.assert_has_calls([mock.call(2), mock.call(3)])


async def test_retries_failed_call_retry_after_header():
    responses = [
        HTTPStatusError(
            "Too many requests",
            request=Request("get", "/"),
            response=Response(429, headers={"Retry-After": "2"}),
        ),
        Response(200),
    ]

    requester = AsyncMock()
    requester.side_effect = responses

    with mock.patch(
        "prefect.concurrency.asyncio.bounded_poisson_interval"
    ) as bounded_poisson_interval:
        with mock.patch("prefect.concurrency.asyncio.asyncio.sleep") as sleep:
            bounded_poisson_interval.side_effect = [2.0]

            result = await wait_for_successful_response(requester)
            assert result == responses[1]

            # In the case of a `Retry-After` header `bounded_poisson_interval`
            # is called with the value of the header as the lower bounds and
            # `retry_after * (1.0 + jitter)` as the upper bounds, the result of
            # which is then passed to `sleep`.
            bounded_poisson_interval.assert_called_once_with(
                2.0, 2.0 * (1.0 + PREFECT_CLIENT_RETRY_JITTER_FACTOR.value())
            )
            sleep.assert_called_once_with(2.0)


async def test_failed_call_status_code_not_retryable():
    response = HTTPStatusError(
        "Too many requests",
        request=Request("get", "/"),
        response=Response(500, headers={"Retry-After": "2"}),
    )
    requester = AsyncMock()
    requester.side_effect = response

    with pytest.raises(HTTPStatusError):
        await wait_for_successful_response(requester)
