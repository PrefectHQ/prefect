import sys
from unittest.mock import MagicMock

import pytest
from httpx import Request, Response

from prefect.utilities.httpx import PrefectHttpxClient

# AsyncMock has a new import path in Python 3.8+

if sys.version_info < (3, 8):
    # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.AsyncMock
    from mock import AsyncMock
else:
    from unittest.mock import AsyncMock


async def test_prefect_httpx_client_retries_429s():
    client = PrefectHttpxClient()
    client.send = AsyncMock()
    retry_response = Response(
        429,
        headers={"Retry-After": "0"},
        request=Request("a test request", "fake.url/fake/route"),
    )
    success_response = Response(
        200,
        request=Request("a test request", "fake.url/fake/route"),
    )
    client.send.side_effect = [
        retry_response,
        retry_response,
        retry_response,
        retry_response,
        success_response,
    ]
    response = await client.post(
        url="fake.url/fake/route", data={"evenmorefake": "data"}
    )
    assert response.status_code == 200
    client.send.call_count == 5


async def test_prefect_httpx_client_retries_429s_up_to_five_times():
    client = PrefectHttpxClient()
    client.send = AsyncMock()
    retry_response = Response(
        429,
        headers={"Retry-After": "0"},
        request=Request("a test request", "fake.url/fake/route"),
    )
    success_response = Response(
        200,
        request=Request("a test request", "fake.url/fake/route"),
    )
    client.send.side_effect = [
        retry_response,
        retry_response,
        retry_response,
        retry_response,
        retry_response,
        retry_response,
        success_response,
    ]

    response = await client.post(
        url="fake.url/fake/route",
        data={"evenmorefake": "data"},
        raise_for_status=False,
    )

    assert response.status_code == 429
    client.send.call_count == 5
