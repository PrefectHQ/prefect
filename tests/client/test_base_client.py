from unittest.mock import call

import pytest
from fastapi import status
from httpx import (
    AsyncClient,
    HTTPStatusError,
    ReadError,
    RemoteProtocolError,
    Request,
    Response,
)

from prefect.client.base import PrefectHttpxClient
from prefect.testing.utilities import AsyncMock

four_twenty_nine_retry_after_zero = Response(
    status.HTTP_429_TOO_MANY_REQUESTS,
    headers={"Retry-After": "0"},
    request=Request("a test request", "fake.url/fake/route"),
)

four_twenty_nine_no_retry_header = Response(
    status.HTTP_429_TOO_MANY_REQUESTS,
    request=Request("a test request", "fake.url/fake/route"),
)

success_response = Response(
    status.HTTP_200_OK,
    request=Request("a test request", "fake.url/fake/route"),
)


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

    @pytest.mark.parametrize(
        "exception",
        [RemoteProtocolError, ReadError],
    )
    async def test_prefect_httpx_client_retries_on_designated_exceptions(
        self,
        monkeypatch,
        exception,
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()

        base_client_send.side_effect = [
            exception("msg"),
            exception("msg"),
            exception("msg"),
            success_response,
        ]
        response = await client.post(
            url="fake.url/fake/route", data={"evenmorefake": "data"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert base_client_send.call_count == 4

    @pytest.mark.parametrize(
        "causes_of_retries,final_exception,text_match",
        [
            ([four_twenty_nine_retry_after_zero] * 7, HTTPStatusError, "429"),
            ([RemoteProtocolError("msg")] * 7, RemoteProtocolError, None),
            (
                [RemoteProtocolError("msg")] * 3
                + ([four_twenty_nine_retry_after_zero] * 4),
                HTTPStatusError,
                "429",
            ),
        ],
    )
    async def test_prefect_httpx_client_retries_up_to_five_times(
        self,
        monkeypatch,
        causes_of_retries,
        final_exception,
        text_match,
        mock_anyio_sleep,
    ):
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        # Return more than 6 retry responses
        base_client_send.side_effect = causes_of_retries

        with pytest.raises(final_exception, match=text_match):
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

        base_client_send.side_effect = [
            retry_response,
            success_response,
        ]

        with mock_anyio_sleep.assert_sleeps_for(5):
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(
        "cause_of_retry",
        [four_twenty_nine_no_retry_header, RemoteProtocolError("msg")],
    )
    async def test_prefect_httpx_client_falls_back_to_exponential_backoff(
        self, mock_anyio_sleep, cause_of_retry, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        base_client_send.side_effect = [
            cause_of_retry,
            cause_of_retry,
            cause_of_retry,
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

    async def test_prefect_httpx_client_does_not_retry_other_exceptions(
        self, mock_anyio_sleep, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        base_client_send.side_effect = [TypeError("This error should not be retried")]

        with pytest.raises(TypeError):
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )

        mock_anyio_sleep.assert_not_called()
