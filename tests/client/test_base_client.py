from unittest.mock import call

import httpx
import pytest
from httpx import AsyncClient, Request, Response
from prefect._vendor.starlette import status

from prefect.client.base import PrefectHttpxClient, PrefectResponse
from prefect.exceptions import PrefectHTTPStatusError
from prefect.settings import (
    PREFECT_CLIENT_MAX_RETRIES,
    PREFECT_CLIENT_RETRY_EXTRA_CODES,
    PREFECT_CLIENT_RETRY_JITTER_FACTOR,
    temporary_settings,
)
from prefect.testing.utilities import AsyncMock

RESPONSE_429_RETRY_AFTER_0 = Response(
    status.HTTP_429_TOO_MANY_REQUESTS,
    headers={"Retry-After": "0"},
    request=Request("a test request", "fake.url/fake/route"),
)

RESPONSE_429_RETRY_AFTER_MISSING = Response(
    status.HTTP_429_TOO_MANY_REQUESTS,
    request=Request("a test request", "fake.url/fake/route"),
)


RESPONSE_200 = Response(
    status.HTTP_200_OK,
    request=Request("a test request", "fake.url/fake/route"),
)


@pytest.fixture
def disable_jitter():
    with temporary_settings({PREFECT_CLIENT_RETRY_JITTER_FACTOR: 0}):
        yield


class TestPrefectHttpxClient:
    @pytest.mark.usefixtures("mock_anyio_sleep", "disable_jitter")
    @pytest.mark.parametrize(
        "error_code",
        [
            status.HTTP_408_REQUEST_TIMEOUT,
            status.HTTP_429_TOO_MANY_REQUESTS,
            status.HTTP_503_SERVICE_UNAVAILABLE,
            status.HTTP_502_BAD_GATEWAY,
        ],
    )
    async def test_prefect_httpx_client_retries_on_designated_error_codes(
        self, monkeypatch, error_code, caplog
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()
        retry_response = Response(
            error_code,
            request=Request("a test request", "fake.url/fake/route"),
        )
        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            RESPONSE_200,
        ]
        async with client:
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK
        assert base_client_send.call_count == 4

        # We log on retry
        assert "Received response with retryable status code" in caplog.text
        assert "Another attempt will be made in 2s" in caplog.text
        assert "This is attempt 1/6" in caplog.text

        # A traceback should not be included
        assert "Traceback" not in caplog.text

        # Ensure the messaging changes
        assert "Another attempt will be made in 4s" in caplog.text
        assert "This is attempt 2/6" in caplog.text

    @pytest.mark.usefixtures("mock_anyio_sleep", "disable_jitter")
    @pytest.mark.parametrize(
        "error_code,extra_codes",
        [
            (status.HTTP_508_LOOP_DETECTED, "508"),
            (status.HTTP_409_CONFLICT, "508,409"),
        ],
    )
    async def test_prefect_httpx_client_retries_on_extra_error_codes(
        self, monkeypatch, error_code, extra_codes, caplog
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()
        retry_response = Response(
            error_code,
            request=Request("a test request", "fake.url/fake/route"),
        )
        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            RESPONSE_200,
        ]
        with temporary_settings({PREFECT_CLIENT_RETRY_EXTRA_CODES: extra_codes}):
            async with client:
                response = await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )
        assert response.status_code == status.HTTP_200_OK
        assert base_client_send.call_count == 4

        # We log on retry
        assert "Received response with retryable status code" in caplog.text
        assert "Another attempt will be made in 2s" in caplog.text
        assert "This is attempt 1/6" in caplog.text

        # A traceback should not be included
        assert "Traceback" not in caplog.text

        # Ensure the messaging changes
        assert "Another attempt will be made in 4s" in caplog.text
        assert "This is attempt 2/6" in caplog.text

    @pytest.mark.usefixtures("mock_anyio_sleep", "disable_jitter")
    async def test_prefect_httpx_client_raises_on_non_extra_error_codes(
        self, monkeypatch, caplog
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()
        retry_response = Response(
            status.HTTP_508_LOOP_DETECTED,
            request=Request("a test request", "fake.url/fake/route"),
        )
        base_client_send.side_effect = [
            retry_response,
            retry_response,
            retry_response,
            RESPONSE_200,
        ]
        with temporary_settings({PREFECT_CLIENT_RETRY_EXTRA_CODES: "409"}):
            with pytest.raises(PrefectHTTPStatusError):
                async with client:
                    await client.post(
                        url="fake.url/fake/route", data={"evenmorefake": "data"}
                    )

    @pytest.mark.usefixtures("mock_anyio_sleep", "disable_jitter")
    @pytest.mark.parametrize(
        "exception_type",
        [
            httpx.RemoteProtocolError,
            httpx.ReadError,
            httpx.WriteError,
            httpx.LocalProtocolError,
            httpx.PoolTimeout,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
        ],
    )
    async def test_prefect_httpx_client_retries_on_designated_exceptions(
        self,
        monkeypatch,
        exception_type,
        caplog,
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)
        client = PrefectHttpxClient()

        base_client_send.side_effect = [
            exception_type("test"),
            exception_type("test"),
            exception_type("test"),
            RESPONSE_200,
        ]
        async with client:
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK
        assert base_client_send.call_count == 4

        # We log on retry
        assert "Encountered retryable exception during request" in caplog.text
        assert "Another attempt will be made in 2s" in caplog.text
        assert "This is attempt 1/6" in caplog.text

        # The traceback should be included
        assert "Traceback" in caplog.text

        # Ensure the messaging changes
        assert "Another attempt will be made in 4s" in caplog.text
        assert "This is attempt 2/6" in caplog.text

    @pytest.mark.usefixtures("mock_anyio_sleep")
    @pytest.mark.parametrize(
        "response_or_exc",
        [RESPONSE_429_RETRY_AFTER_0, httpx.RemoteProtocolError("test")],
    )
    async def test_prefect_httpx_client_retries_up_to_five_times(
        self,
        monkeypatch,
        response_or_exc,
    ):
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        # Return more than 6 retryable responses
        base_client_send.side_effect = [response_or_exc] * 10

        with pytest.raises(Exception):
            async with client:
                await client.post(
                    url="fake.url/fake/route",
                    data={"evenmorefake": "data"},
                )

        # 5 retries + 1 first attempt
        assert base_client_send.call_count == 6

    @pytest.mark.usefixtures("mock_anyio_sleep")
    @pytest.mark.parametrize(
        "response_or_exc",
        [RESPONSE_429_RETRY_AFTER_0, httpx.RemoteProtocolError("test")],
    )
    async def test_prefect_httpx_client_respects_max_retry_setting(
        self,
        monkeypatch,
        response_or_exc,
    ):
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        # Return more than 10 retryable responses
        base_client_send.side_effect = [response_or_exc] * 20

        with pytest.raises(Exception):
            with temporary_settings({PREFECT_CLIENT_MAX_RETRIES: 10}):
                async with client:
                    await client.post(
                        url="fake.url/fake/route",
                        data={"evenmorefake": "data"},
                    )

        # 10 retries + 1 first attempt
        assert base_client_send.call_count == 11

    @pytest.mark.usefixtures("mock_anyio_sleep")
    @pytest.mark.parametrize(
        "final_response,expected_error_type",
        [
            (
                RESPONSE_429_RETRY_AFTER_0,
                httpx.HTTPStatusError,
            ),
            (httpx.RemoteProtocolError("test"), httpx.RemoteProtocolError),
        ],
    )
    async def test_prefect_httpx_client_raises_final_error_after_retries(
        self, monkeypatch, final_response, expected_error_type
    ):
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        # First throw a bunch of retryable errors, then the final one
        base_client_send.side_effect = [httpx.ReadError("test")] * 5 + [final_response]

        with pytest.raises(expected_error_type):
            async with client:
                await client.post(
                    url="fake.url/fake/route",
                    data={"evenmorefake": "data"},
                )

        # 5 retries + 1 first attempt
        assert base_client_send.call_count == 6

    @pytest.mark.parametrize(
        "error_code",
        [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_503_SERVICE_UNAVAILABLE],
    )
    @pytest.mark.usefixtures("disable_jitter")
    async def test_prefect_httpx_client_respects_retry_header(
        self, monkeypatch, mock_anyio_sleep, error_code
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()
        retry_response = Response(
            error_code,
            headers={"Retry-After": "5"},
            request=Request("a test request", "fake.url/fake/route"),
        )

        base_client_send.side_effect = [
            retry_response,
            RESPONSE_200,
        ]

        with mock_anyio_sleep.assert_sleeps_for(5):
            async with client:
                response = await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.usefixtures("disable_jitter")
    @pytest.mark.parametrize(
        "response_or_exc",
        [RESPONSE_429_RETRY_AFTER_MISSING, httpx.RemoteProtocolError("test")],
    )
    async def test_prefect_httpx_client_uses_exponential_backoff_without_retry_after_header(
        self, mock_anyio_sleep, response_or_exc, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        base_client_send.side_effect = [
            response_or_exc,
            response_or_exc,
            response_or_exc,
            RESPONSE_200,
        ]

        with mock_anyio_sleep.assert_sleeps_for(2 + 4 + 8):
            async with client:
                response = await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )
        assert response.status_code == status.HTTP_200_OK
        mock_anyio_sleep.assert_has_awaits([call(2), call(4), call(8)])

    @pytest.mark.usefixtures("disable_jitter")
    async def test_prefect_httpx_client_respects_retry_header_per_response(
        self, mock_anyio_sleep, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        base_client_send.side_effect = [
            # Generate responses with retry after headers
            Response(
                status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)},
                request=Request("a test request", "fake.url/fake/route"),
            )
            for retry_after in [5, 0, 10, 2.0]
        ] + [RESPONSE_200]  # Then succeed

        with mock_anyio_sleep.assert_sleeps_for(5 + 10 + 2):
            async with client:
                response = await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )
        assert response.status_code == status.HTTP_200_OK
        mock_anyio_sleep.assert_has_awaits([call(5), call(0), call(10), call(2.0)])

    async def test_prefect_httpx_client_adds_jitter_with_retry_header(
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
            retry_response,
            retry_response,
            retry_response,
            retry_response,
            RESPONSE_200,
        ]

        async with client:
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert response.status_code == status.HTTP_200_OK

        for mock_call in mock_anyio_sleep.mock_calls:
            sleep_time = mock_call.args[0]
            assert sleep_time > 5 and sleep_time < (5 * 1.2)

    @pytest.mark.parametrize(
        "response_or_exc",
        [RESPONSE_429_RETRY_AFTER_MISSING, httpx.RemoteProtocolError("test")],
    )
    async def test_prefect_httpx_client_adds_jitter_with_exponential_backoff(
        self, mock_anyio_sleep, response_or_exc, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        base_client_send.side_effect = [
            response_or_exc,
            response_or_exc,
            response_or_exc,
            RESPONSE_200,
        ]

        with mock_anyio_sleep.assert_sleeps_for(
            2 + 4 + 8,
            extra_tolerance=0.2 * 14,  # Add tolerance for jitter
        ):
            async with client:
                response = await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )
        assert response.status_code == status.HTTP_200_OK
        mock_anyio_sleep.assert_has_awaits(
            [call(pytest.approx(n, rel=0.2)) for n in [2, 4, 8]]
        )

    async def test_prefect_httpx_client_does_not_retry_other_exceptions(
        self, mock_anyio_sleep, monkeypatch
    ):
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        client = PrefectHttpxClient()

        base_client_send.side_effect = [TypeError("This error should not be retried")]

        with pytest.raises(TypeError, match="This error should not be retried"):
            async with client:
                await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )

        mock_anyio_sleep.assert_not_called()

    async def test_prefect_httpx_client_returns_prefect_response(self, monkeypatch):
        """Test that the PrefectHttpxClient returns a PrefectResponse"""
        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        base_client_send.return_value = RESPONSE_200

        async with client:
            response = await client.post(
                url="fake.url/fake/route", data={"evenmorefake": "data"}
            )
        assert isinstance(response, PrefectResponse)

    #
    async def test_prefect_httpx_client_raises_prefect_http_status_error(
        self, monkeypatch
    ):
        RESPONSE_400 = Response(
            status.HTTP_400_BAD_REQUEST,
            json={"extra_info": [{"message": "a test error message"}]},
            request=Request("a test request", "fake.url/fake/route"),
        )

        client = PrefectHttpxClient()
        base_client_send = AsyncMock()
        monkeypatch.setattr(AsyncClient, "send", base_client_send)

        base_client_send.return_value = RESPONSE_400
        with pytest.raises(PrefectHTTPStatusError) as exc:
            async with client:
                await client.post(
                    url="fake.url/fake/route", data={"evenmorefake": "data"}
                )
        expected = "Response: {'extra_info': [{'message': 'a test error message'}]}"
        assert expected in str(exc.exconly())
