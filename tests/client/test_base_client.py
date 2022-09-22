from unittest.mock import call

import pytest
from fastapi import status
from httpx import AsyncClient, HTTPStatusError, Request, Response

from prefect.client.base import PrefectHttpxClient
from prefect.testing.utilities import AsyncMock


class TestPrefectHttpxClient:
    @pytest.mark.parametrize(
        "error_code",
        [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_503_SERVICE_UNAVAILABLE],
    )
    async def test_prefect_httpx_client_retries_on_designated_error_codes(
        self, monkeypatch, error_code
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()
        retry_response = Response(
            error_code,
            headers={"Retry-After": "0"},
            request=Request("a test request", "fake.url/fake/route"),
        )
        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )
        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            success_response,
        ]
        response = await client.post(
            url="fake.url/fake/route", data={"evenmorefake": "data"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert base_client_send.call_count == 4

    async def test_prefect_httpx_client_retries_429s_up_to_five_times(
        self, monkeypatch
    ):
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": "0"},
            request=Request("a test request", "fake.url/fake/route"),
        )

        # Return more than 6 retry responses
        base_client_send.side_effect = [retry_response] * 7

        with pytest.raises(HTTPStatusError, match="429"):
            await client.post(
                url="fake.url/fake/route",
                data={"evenmorefake": "data"},
            )

        # 5 retries + 1 first attempt
        assert base_client_send.call_count == 6

    async def test_prefect_httpx_client_respects_retry_header(
        self, monkeypatch, mock_anyio_sleep
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()
        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": "5"},
            request=Request("a test request", "fake.url/fake/route"),
        )

        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            retry_response,
            success_response,
        ]

        with mock_anyio_sleep.assert_sleeps_for(5):
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK

    async def test_prefect_httpx_client_falls_back_to_exponential_backoff(
        self, mock_anyio_sleep, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()
        retry_response = Response(
            status.HTTP_429_TOO_MANY_REQUESTS,
            request=Request("a test request", "fake.url/fake/route"),
        )

        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            success_response,
        ]

        with mock_anyio_sleep.assert_sleeps_for(2 + 4 + 8):
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK
        mock_anyio_sleep.assert_has_awaits([call(2), call(4), call(8)])

    async def test_prefect_httpx_client_respects_retry_header_per_response(
        self, mock_anyio_sleep, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        def make_retry_response(retry_after):
            return Response(
                status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                request=Request("a test request", "fake.url/fake/route"),
            )

        success_response = Response(
            status.HTTP_200_OK,
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            make_retry_response(5),
            make_retry_response(0),
            make_retry_response(10),
            make_retry_response(2.0),
            success_response,
        ]

        with mock_anyio_sleep.assert_sleeps_for(5 + 10 + 2):
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK
        mock_anyio_sleep.assert_has_awaits([call(5), call(0), call(10), call(2.0)])
